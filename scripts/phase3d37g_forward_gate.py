#!/usr/bin/env python3
"""Phase 3D37G: read-only forward-only gate on diagnostic sample previews.

Never creates authentic predictions, never writes Supabase, and never backfills.
"""
import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from phase3d36c_supabase_stats import fetch_latest
from phase3d37b_roster_match import BASE, athletes, fetch, games, teams, verify
from phase3d37c_crosswalk import utc
from phase3d37d_readiness import run as readiness_run
from phase3d37f_pregame import current_week, freshness

UTC = timezone.utc
ALLOWED = {
    'QB': {'pass_yards', 'pass_attempts', 'rush_yards', 'rush_attempts'},
    'RB': {'rush_yards', 'rush_attempts', 'rec_yards', 'receptions', 'targets'},
    'WR': {'rec_yards', 'receptions', 'targets', 'rush_yards', 'rush_attempts'},
    'TE': {'rec_yards', 'receptions', 'targets'},
}


def metric_allowed(position, metric, value):
    return position in ALLOWED and metric in ALLOWED[position] and isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def stable_key(season, week, game_id, espn_id, metric):
    """Logical identity intentionally excludes export fingerprint and run time."""
    if not all(str(x).isdigit() for x in (season, week, game_id, espn_id)) or metric not in {m for s in ALLOWED.values() for m in s}:
        raise ValueError('invalid_prediction_identity')
    return f'{season}/{week}/{game_id}/{espn_id}/{metric}'


def evaluate(samples, roster, schedule, now, season, week, generated, max_age_hours=12, lead_minutes=30):
    reason = freshness(generated, now, max_age_hours)
    schedule_by_id = {str(g['game_id']): g for g in schedule}
    matched = {m['player_id']: m for m in verify(roster, schedule, now) if m['status'] == 'matched'}
    positions = {}
    for pid, records in roster.items():
        if len(records) == 1:
            positions[pid] = records[0].get('position')
    counts = Counter()
    results = []
    seen = set()
    for p in samples:
        pid, gid = str(p.get('espn_id', '')), str(p.get('game_id', ''))
        game = schedule_by_id.get(gid)
        match = matched.get(pid)
        kickoff = utc(p.get('kickoff_at'))
        if reason:
            counts[reason] += 1; continue
        if not game or not match or match['game_id'] != gid:
            counts['unverified_current_matchup'] += 1; continue
        if not kickoff or kickoff != utc(game.get('kickoff_at')) or kickoff <= now + timedelta(minutes=lead_minutes):
            counts['kickoff_not_safely_ahead'] += 1; continue
        if str(game.get('status', '')).lower() not in ('status_scheduled', 'scheduled', 'pre'):
            counts['game_not_scheduled'] += 1; continue
        pos = positions.get(pid)
        if pos not in ALLOWED:
            counts['unknown_or_unsupported_position'] += 1; continue
        if not isinstance(p.get('metrics'), dict):
            counts['invalid_metrics'] += 1; continue
        for metric, data in p['metrics'].items():
            baseline = data.get('baseline') if isinstance(data, dict) else None
            if not metric_allowed(pos, metric, baseline):
                counts['inapplicable_or_zero_metric'] += 1; continue
            key = stable_key(season, week, gid, pid, metric)
            if key in seen:
                counts['duplicate_logical_identity'] += 1; continue
            seen.add(key)
            results.append({'logical_key': key, 'espn_id': pid, 'position': pos, 'game_id': gid,
                            'kickoff_at': kickoff.isoformat(), 'metric': metric, 'baseline': baseline})
            counts['preview_metrics_passed'] += 1
    return {'status_counts': dict(counts), 'filtered_sample_previews': results[:30],
            'sample_metrics_passed': len(results), 'sample_players_passed': len({x['espn_id'] for x in results}),
            'source_freshness_issue': reason}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int)
    ap.add_argument('--week', type=int)
    ap.add_argument('--output', default='phase3d37g-report.json')
    args = ap.parse_args()
    now = datetime.now(UTC)
    if args.season is None or args.week is None:
        yr, wk = current_week(fetch(BASE + '/scoreboard?limit=100'))
        season, week = args.season or yr, args.week or wk
    else:
        season, week = args.season, args.week
    if not 2000 <= season <= 2100 or not 1 <= week <= 18:
        raise ValueError('invalid_season_week')
    source = fetch_latest(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'], season)
    if not source or not source.get('csv_text'):
        raise ValueError('missing_export')
    readiness = readiness_run(season, week)
    if readiness.get('status') != 'ok' or readiness.get('export_generated_at') != source.get('generated_at'):
        raise ValueError('readiness_failed_or_source_changed')
    team_list = teams(fetch(BASE + '/teams?limit=50'))
    if len(team_list) != 32 or len({str(t['id']) for t in team_list}) != 32:
        raise ValueError('incomplete_teams')
    roster = defaultdict(list)
    for team in team_list:
        tid = str(team['id'])
        for player in athletes(fetch(BASE + f'/teams/{tid}/roster')):
            pid = str(player.get('id', ''))
            if pid:
                pos = player.get('position', {})
                pos = pos.get('abbreviation') if isinstance(pos, dict) else None
                roster[pid].append({'team_id': tid, 'position': pos})
    schedule = games(fetch(BASE + f'/scoreboard?dates={season}&week={week}&seasontype=2&limit=1000'))
    if not schedule:
        raise ValueError('missing_schedule')
    sample = readiness.get('sample_previews', [])
    evaluated = evaluate(sample, roster, schedule, now, season, week, source.get('generated_at'))
    report = {
        'phase': '3D37G', 'mode': 'READ_ONLY_DIAGNOSTIC_SAMPLE', 'season': season, 'week': week,
        'run_at_utc': now.isoformat(), 'source_generated_at': source.get('generated_at'),
        'source_sha256': hashlib.sha256(source['csv_text'].encode('utf-8')).hexdigest(),
        'readiness_recomputed_players': readiness.get('recomputed_player_count', 0),
        'readiness_recomputed_metrics': readiness.get('recomputed_metric_count', 0),
        'diagnostic_sample_players_checked': len(sample), 'sample_only_not_full_population': True,
        'roster_players': len(roster), 'scheduled_games': len(schedule), **evaluated,
        'readiness': 'BLOCKED_FOR_AUTOMATED_SNAPSHOTS', 'forward_capture_evidence': 'RUN_TIME_ONLY',
        'point_in_time_upstream_publication_verified': False,
        'snapshots_created': 0, 'grades_created': 0, 'database_writes': 0,
        'next_required': ['Generate full candidate set, not readiness diagnostic samples',
                          'Capture fresh immutable input for each kickoff window',
                          'Verify source generation and upstream provenance',
                          'Review schema/RLS and obtain explicit approval before any database writes'],
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('season','week','readiness','diagnostic_sample_players_checked','sample_metrics_passed','source_freshness_issue','database_writes')}))


if __name__ == '__main__':
    main()
