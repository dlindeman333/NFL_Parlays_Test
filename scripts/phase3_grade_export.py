"""Deterministic, offline grading artifact for future reviewed persistence.

Does not write to Supabase. Refuses incomplete or unverified grading batches.
"""
import argparse
import hashlib
import json
from pathlib import Path
from phase3_postgame_grading_gate import run


def build_export(snapshots_path, stats_path):
    gate = run(snapshots_path, stats_path)
    if not gate['ready']:
        return {'mode': 'GRADE_EXPORT_BLOCKED', 'ready': False,
                'reason': gate.get('reason', 'Grading readiness failed'),
                'database_writes': 0, 'rows': []}
    snapshots = json.loads(Path(snapshots_path).read_text(encoding='utf-8'))
    by_game = {(s['season'], s['week'], str(s['game_id'])): s for s in snapshots}
    rows = []
    for result in gate['preview']['results']:
        if result['status'] not in ('HIT', 'MISS', 'PUSH'):
            raise ValueError('Incomplete grade cannot be exported')
        key = (result['season'], result['week'], result['game_id'])
        snap = by_game[key]
        pick = snap['picks'][result['pick_index']]
        canonical = json.dumps({'season': key[0], 'week': key[1], 'game_id': key[2],
                                'captured_at': snap['captured_at'], 'pick_index': result['pick_index'],
                                'pick': pick}, sort_keys=True, separators=(',', ':'), allow_nan=False)
        rows.append({'tracking_id': hashlib.sha256(canonical.encode('utf-8')).hexdigest(),
                     'season': key[0], 'week': key[1], 'game_id': key[2],
                     'pick_index': result['pick_index'], 'grade': result['status'],
                     'actual': result['actual'], 'capture_time': snap['captured_at'],
                     'provenance_status': 'VERIFIED_PREGAME'})
    return {'mode': 'OFFLINE_GRADE_EXPORT', 'ready': True, 'database_writes': 0,
            'rows': sorted(rows, key=lambda r: r['tracking_id'])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshots', required=True)
    parser.add_argument('--stats', required=True)
    parser.add_argument('--output', default='phase3-grade-export.json')
    args = parser.parse_args()
    artifact = build_export(args.snapshots, args.stats)
    Path(args.output).write_text(json.dumps(artifact, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ready': artifact['ready'], 'rows': len(artifact['rows']), 'database_writes': 0}))


if __name__ == '__main__':
    main()
