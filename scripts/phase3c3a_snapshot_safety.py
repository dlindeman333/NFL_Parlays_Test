#!/usr/bin/env python3
"""Read-only snapshot safety preview. NEVER writes to Supabase.

Runs the existing Phase 3C-2 prediction preview, then applies conservative
snapshot eligibility checks. This is NOT an authorization to archive predictions.
"""
import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path('phase3c3a-report')
MAX_EXPORT_AGE_HOURS = 72
MIN_COMPLETED_GAMES = 3
MIN_LEAD_MINUTES = 60
MAX_KICKOFF_DAYS = 7
ALIASES = {'JAX': 'JAC', 'JAC': 'JAC', 'LAR': 'LA', 'LA': 'LA', 'WSH': 'WAS', 'WAS': 'WAS'}

def normalize(team):
    value = str(team).strip().upper()
    return ALIASES.get(value, value)

def parse_utc(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None

def main():
    OUT.mkdir(exist_ok=True)
    env = os.environ.copy()
    result = subprocess.run([sys.executable, 'scripts/phase3c2_preview.py'],
                            env=env, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError('Prediction preview failed: ' + result.stderr[-1500:])
    source = Path('phase3c2-report/preview.json')
    if not source.is_file():
        raise RuntimeError('Missing phase3c2-report/preview.json')
    preview = json.loads(source.read_text())
    now = datetime.now(timezone.utc)
    export_time = parse_utc(preview.get('export_generated_at'))
    age_hours = ((now - export_time).total_seconds() / 3600) if export_time else None
    source_fresh = age_hours is not None and 0 <= age_hours <= MAX_EXPORT_AGE_HOURS
    # A passing parity report validates a prior sample, not the current export.
    # Explicitly do NOT assert parity or current roster availability.
    keys = Counter()
    records = []
    for item in preview.get('predictions', []):
        reasons = []
        kickoff = parse_utc(item.get('kickoff_utc'))
        if not source_fresh:
            reasons.append('STATS_EXPORT_NOT_FRESH_OR_TIMESTAMP_INVALID')
        if kickoff is None:
            reasons.append('INVALID_KICKOFF_UTC')
        else:
            remaining = kickoff - now
            if remaining <= timedelta(minutes=MIN_LEAD_MINUTES):
                reasons.append('KICKOFF_TOO_CLOSE_OR_PASSED')
            if remaining > timedelta(days=MAX_KICKOFF_DAYS):
                reasons.append('KICKOFF_OUTSIDE_7_DAY_ARCHIVE_WINDOW')
        if int(item.get('historical_games') or 0) < MIN_COMPLETED_GAMES:
            reasons.append('INSUFFICIENT_COMPLETED_PLAYER_GAMES')
        if item.get('market') not in ('ps', 'ru', 'td'):
            reasons.append('UNSUPPORTED_MARKET')
        if item.get('market') in ('ps', 'ru') and not isinstance(item.get('reference_line'), (int, float)):
            reasons.append('MISSING_REFERENCE_LINE')
        try:
            away, home = [normalize(v) for v in item.get('game', '').split(' @ ')]
            team = normalize(item.get('team'))
            if team not in (away, home):
                reasons.append('PLAYER_TEAM_NOT_IN_MATCHUP')
        except ValueError:
            reasons.append('INVALID_MATCHUP')
            away = home = ''
        # Candidate key is a simulation; real database unique keys/schema must be reviewed.
        key_parts = [str(preview.get('mode')), '2026', str(item.get('week')),
                     away, home, team, str(item.get('player')).strip().lower(),
                     str(item.get('market')), str(item.get('reference_line'))]
        key = hashlib.sha256('|'.join(key_parts).encode()).hexdigest()[:24]
        keys[key] += 1
        records.append({'candidate_id': key, 'week': item.get('week'),
                        'game': item.get('game'), 'kickoff_utc': item.get('kickoff_utc'),
                        'player': item.get('player'), 'market': item.get('market'),
                        'projection': item.get('projection'),
                        'probability': item.get('model_over_probability'),
                        'historical_games': item.get('historical_games'),
                        'reasons': reasons})
    for item in records:
        if keys[item['candidate_id']] > 1:
            item['reasons'].append('DUPLICATE_CANDIDATE_IN_PREVIEW')
        item['status'] = 'WOULD_PASS_BASIC_CHECKS' if not item['reasons'] else 'BLOCKED'
    counts = Counter(item['status'] for item in records)
    blockers = Counter(reason for item in records for reason in item['reasons'])
    report = {
        'mode': 'READ_ONLY_SNAPSHOT_SAFETY_SIMULATION',
        'generated_utc': now.isoformat(),
        'source_export_generated_at': preview.get('export_generated_at'),
        'source_export_age_hours': round(age_hours, 2) if age_hours is not None else None,
        'source_fresh': source_fresh,
        'rules': {'max_export_age_hours': MAX_EXPORT_AGE_HOURS,
                  'min_completed_player_games': MIN_COMPLETED_GAMES,
                  'min_minutes_before_kickoff': MIN_LEAD_MINUTES,
                  'max_days_before_kickoff': MAX_KICKOFF_DAYS},
        'candidate_count': len(records), 'would_pass_basic_checks': counts['WOULD_PASS_BASIC_CHECKS'],
        'blocked': counts['BLOCKED'], 'block_reasons': dict(blockers),
        'upstream_blocked_games': preview.get('blocked_games', []),
        'not_verified': [
            'No actual Supabase snapshot-table schema, unique indexes, RLS, or existing snapshot rows checked',
            'No duplicate detection against Supabase; candidate IDs are simulated only',
            'No current roster, injury, official game-finality or sportsbook odds verification',
            'No live browser execution or parity recheck on the current export',
            'Static bundled team ratings and provisional future player assignments remain',
            'A basic-check pass is NOT permission to archive or schedule writes'
        ], 'database_writes': 0, 'records': records
    }
    (OUT/'safety-preview.json').write_text(json.dumps(report, indent=2))
    with (OUT/'safety-preview.csv').open('w', newline='') as fh:
        cols = ['candidate_id', 'week', 'game', 'kickoff_utc', 'player', 'market',
                'projection', 'probability', 'historical_games', 'status', 'reasons']
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for item in records:
            writer.writerow({**item, 'reasons': '; '.join(item['reasons'])})
    print(json.dumps({k: report[k] for k in ('mode', 'source_export_generated_at',
          'source_export_age_hours', 'source_fresh', 'candidate_count',
          'would_pass_basic_checks', 'blocked', 'block_reasons', 'database_writes')}, indent=2))
    print('READ ONLY: No snapshot writes, no schedule, no DB mutations.')
    if not records:
        print('WARNING: no candidates; inspect upstream_blocked_games in report.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        OUT.mkdir(exist_ok=True)
        (OUT/'error.txt').write_text(str(exc))
        print('SAFETY PREVIEW FAILED:', exc, file=sys.stderr)
        sys.exit(1)
