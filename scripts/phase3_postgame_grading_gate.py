#!/usr/bin/env python3
"""Fail-closed postgame grading readiness: offline, read-only, no Supabase access."""
import argparse
import csv
import json
import datetime as dt
from pathlib import Path
from nfl_readonly_grader import audit


def parse_utc(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Missing timestamp')
    timestamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError('Timestamp must include timezone')
    return timestamp.astimezone(dt.timezone.utc)


def validate_snapshot(snap):
    if not isinstance(snap, dict) or snap.get('provenance_status') != 'VERIFIED_PREGAME':
        return 'Snapshot missing VERIFIED_PREGAME provenance'
    try:
        captured = parse_utc(snap.get('captured_at'))
        kickoff = parse_utc(snap.get('kickoff_at'))
    except (ValueError, TypeError, OverflowError):
        return 'Snapshot missing valid timezone-aware capture/kickoff timestamps'
    if captured >= kickoff:
        return 'Snapshot was not captured before kickoff'
    if not isinstance(snap.get('picks'), list) or not snap['picks']:
        return 'Snapshot must contain at least one saved pick'
    return None


def run(snapshot_path=None, stats_path=None):
    if not snapshot_path or not stats_path:
        return {'mode': 'POSTGAME_READINESS_ONLY', 'ready': False,
                'reason': 'Verified immutable pregame snapshots and final statistics must both be supplied',
                'database_writes': 0, 'grades_persisted': 0}
    snaps = json.loads(Path(snapshot_path).read_text(encoding='utf-8'))
    if not isinstance(snaps, list):
        raise ValueError('Snapshot input must be a list')
    with open(stats_path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        stats = list(reader)
    if not stats:
        return {'mode': 'POSTGAME_READINESS_ONLY', 'ready': False,
                'reason': 'Final statistics input is empty', 'database_writes': 0, 'grades_persisted': 0}
    # Never grade missing/unknown provenance as authentic pregame predictions.
    seen = set()
    for snap in snaps:
        reason = validate_snapshot(snap)
        if reason:
            return {'mode': 'POSTGAME_READINESS_ONLY', 'ready': False,
                    'reason': reason,
                    'database_writes': 0, 'grades_persisted': 0}
        if not isinstance(snap.get('season'), int) or not 2000 <= snap['season'] <= 2100 or not isinstance(snap.get('week'), int) or not 1 <= snap['week'] <= 22 or not str(snap.get('game_id') or '').strip():
            return {'mode': 'POSTGAME_READINESS_ONLY', 'ready': False,
                    'reason': 'Snapshot missing valid season/week/game identity', 'database_writes': 0, 'grades_persisted': 0}
        identity = (snap['season'], snap['week'], str(snap['game_id']).strip())
        if identity in seen:
            return {'mode': 'POSTGAME_READINESS_ONLY', 'ready': False,
                    'reason': 'Duplicate snapshot game identity', 'database_writes': 0, 'grades_persisted': 0}
        seen.add(identity)
    preview = audit(snaps, stats)
    if not preview['total_picks'] or preview['summary'].get('UNAVAILABLE', 0) == preview['total_picks']:
        return {'mode': 'POSTGAME_READINESS_ONLY', 'ready': False,
                'reason': 'No picks can be graded from verified completed statistics',
                'database_writes': 0, 'grades_persisted': 0, 'preview': preview}
    # A partially graded card is not a complete postgame result. Keep the
    # preview available for inspection, but do not mark the batch ready.
    unavailable = preview['summary'].get('UNAVAILABLE', 0)
    if unavailable:
        return {'mode': 'POSTGAME_READINESS_ONLY', 'ready': False,
                'reason': f'{unavailable} pick(s) lack completed, gradeable statistics',
                'database_writes': 0, 'grades_persisted': 0, 'preview': preview}
    return {'mode': 'POSTGAME_OFFLINE_PREVIEW', 'ready': True,
            'database_writes': 0, 'grades_persisted': 0,
            'preview': preview}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshots')
    parser.add_argument('--stats')
    parser.add_argument('--output', default='postgame-grading-readiness.json')
    args = parser.parse_args()
    result = run(args.snapshots, args.stats)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('mode', 'ready', 'database_writes', 'grades_persisted')}))


if __name__ == '__main__':
    main()
