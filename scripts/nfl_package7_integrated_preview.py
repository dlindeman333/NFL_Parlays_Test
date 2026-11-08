#!/usr/bin/env python3
"""Read-only integrated grading preview; fail closed for unverified contracts."""
import datetime as dt
import json
import os
import pathlib
from collections import Counter
from nfl_package3_live_audit import get_rows
from nfl_package4_final_evidence import fetch_scoreboard, normalize_games
from nfl_package5_game_stats import check_game, extract_player_evidence, fetch_summary, team
from nfl_package6_pick_match import grade as base_grade, parse_number

COMPOSITES = {
    'pass_completions': ('passing', 'C/ATT', 0),
    'pass_attempts': ('passing', 'C/ATT', 1),
    'passing_completions': ('passing', 'C/ATT', 0),
    'passing_attempts': ('passing', 'C/ATT', 1),
}

def grade_compound(pick, records):
    stat = pick.get('stat')
    if pick.get('market') != 'player' or stat not in COMPOSITES:
        return base_grade(pick, records)
    side = pick.get('side')
    line = parse_number(pick.get('line'))
    if side not in ('o', 'u') or line is None:
        return {'status': 'UNAVAILABLE', 'reason': 'Invalid side or betting line'}
    category, label, idx = COMPOSITES[stat]
    name = str(pick.get('player_name') or '').strip().casefold()
    tm = team(pick.get('team'))
    if not name or not tm:
        return {'status': 'UNAVAILABLE', 'reason': 'Missing player identity'}
    matches = [r for r in records if str(r.get('player_name') or '').strip().casefold() == name and team(r.get('team')) == tm and str(r.get('category') or '').lower() == category]
    if len(matches) != 1:
        return {'status': 'UNAVAILABLE', 'reason': 'Missing or ambiguous player/category match'}
    raw = str((matches[0].get('stats') or {}).get(label) or '')
    parts = raw.split('/')
    if len(parts) != 2 or any(not x.strip().isdigit() for x in parts):
        return {'status': 'UNAVAILABLE', 'reason': 'Invalid C/ATT boxscore evidence'}
    completions, attempts = map(int, parts)
    if completions > attempts:
        return {'status': 'UNAVAILABLE', 'reason': 'Inconsistent C/ATT evidence'}
    actual = (completions, attempts)[idx]
    status = 'PUSH' if actual == line else 'HIT' if (actual > line if side == 'o' else actual < line) else 'MISS'
    return {'status': status, 'actual': actual, 'line': line, 'side': side, 'stat': stat, 'player_id': matches[0].get('player_id')}

def evaluate(snaps, games, summary_fetch=fetch_summary):
    details = []
    counts = Counter()
    games_count = Counter()
    market_inventory = Counter()
    for snap in snaps:
        gid = str(snap.get('game_id') or '')
        game_status = check_game(snap, games.get(gid))
        picks = snap.get('picks')
        if not isinstance(picks, list):
            games_count['INVALID_PICKS_JSON'] += 1
            continue
        records = []
        if game_status == 'FINAL_VERIFIED':
            try:
                records = extract_player_evidence(summary_fetch(gid))
                if not records: game_status = 'NO_BOX_SCORE_RECORDS'
            except (OSError, ValueError, TypeError, KeyError):
                game_status = 'BOX_SCORE_UNAVAILABLE'
        games_count[game_status] += 1
        for i, pick in enumerate(picks):
            if isinstance(pick, dict):
                market_inventory[(str(pick.get('market')), str(pick.get('stat')), str(pick.get('side')))] += 1
            if game_status != 'FINAL_VERIFIED':
                result = {'status': 'UNAVAILABLE', 'reason': 'Game evidence: ' + game_status}
            elif not isinstance(pick, dict):
                result = {'status': 'UNAVAILABLE', 'reason': 'Invalid pick JSON'}
            else:
                result = grade_compound(pick, records)
            counts[result['status']] += 1
            details.append({'game_id': gid, 'pick_index': i, **result})
    return {'mode': 'READ_ONLY_INTEGRATED_GRADE_PREVIEW', 'game_counts': dict(games_count), 'grade_counts': dict(counts), 'picks_evaluated': len(details), 'market_inventory': [{'market': k[0], 'stat': k[1], 'side': k[2], 'count': v} for k,v in sorted(market_inventory.items())], 'results': details, 'database_writes': 0, 'official_grades_written': 0, 'readiness': 'READ_ONLY_REQUIRES_MARKET_CONTRACT_REVIEW_BACKUP_AND_EXPLICIT_WRITE_APPROVAL', 'limitations': ['No game-market grading until exact saved contract is verified', 'No guesswork for combined rushing/receiving stats', 'No production writes or scheduling enabled']}

def main():
    season = int(os.environ.get('NFL_SEASON', '2026'))
    week = int(os.environ.get('NFL_WEEK', '9'))
    if not 2020 <= season <= 2100 or not 1 <= week <= 22: raise ValueError('Invalid season/week')
    snaps = get_rows(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'], 'nfl_prediction_snapshots', {'select': 'season,week,game_id,home_team,away_team,picks', 'season': f'eq.{season}', 'week': f'eq.{week}', 'limit': '1000'})
    report = evaluate(snaps, normalize_games(fetch_scoreboard(season, week)))
    report.update({'season': season, 'week': week, 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
    out = pathlib.Path('package7-output')
    out.mkdir(exist_ok=True)
    (out / 'integrated_grade_preview.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('season','week','game_counts','grade_counts','database_writes','readiness')}))
if __name__ == '__main__': main()
