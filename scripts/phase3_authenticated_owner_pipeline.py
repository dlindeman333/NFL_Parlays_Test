"""TEST-only authenticated read-to-offline-grade-plan bridge. Never writes to Supabase.

Requires real snapshot and final-stat artifacts; does not manufacture predictions.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

from phase3_postgame_owner_plan import build
from phase3_tracking_live_preflight import preflight

TEST_REPOSITORY = 'dlindeman333/NFL_Parlays_Test'


def run(snapshots, stats, output_dir, user_id, base_url, key, token,
        repository=TEST_REPOSITORY, *, preflight_fn=preflight):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    # No stale artifacts may survive a failed owner check or missing inputs.
    for name in ('phase3-owner-tracking-plan.json', 'phase3-grade-export.json'):
        (output / name).unlink(missing_ok=True)
    if repository != TEST_REPOSITORY:
        raise ValueError('Only the designated TEST repository is permitted')
    if not snapshots or not stats or not Path(snapshots).is_file() or not Path(stats).is_file():
        return {'ready': False, 'reason': 'Missing real snapshot or final-stat artifact',
                'database_writes': 0}
    records = []
    evidence = preflight_fn(base_url, key, token, user_id, repository,
                            record_sink=records.append)
    if (not isinstance(evidence, dict)
            or evidence.get('mode') != 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT'
            or evidence.get('authenticated_owner_verified') is not True
            or evidence.get('database_writes') != 0
            or evidence.get('visible_tracking_records') != len(records)):
        raise ValueError('Authenticated owner history evidence is incomplete')
    if any(not isinstance(r, dict) or r.get('user_id') != user_id for r in records):
        raise ValueError('Cloud history includes another owner')
    # Keep raw cloud history out of published artifacts and clean it up after use.
    with tempfile.TemporaryDirectory(prefix='phase3-owner-history-') as temp:
        existing = Path(temp) / 'owner-history.json'
        existing.write_text(json.dumps(records, allow_nan=False), encoding='utf-8')
        result = build(snapshots, stats, existing, user_id, output)
    return {**result, 'mode': 'TEST_AUTHENTICATED_OWNER_DRY_RUN',
            'authenticated_owner_verified': True, 'cloud_writes_enabled': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshots', required=True)
    p.add_argument('--stats', required=True)
    p.add_argument('--output-dir', required=True)
    p.add_argument('--user-id', required=True)
    args = p.parse_args()
    result = run(args.snapshots, args.stats, args.output_dir, args.user_id,
                 os.environ.get('NFL_TEST_SUPABASE_URL', ''),
                 os.environ.get('NFL_TEST_SUPABASE_PUBLISHABLE_KEY', ''),
                 os.environ.get('NFL_TEST_USER_ACCESS_TOKEN', ''),
                 os.environ.get('GITHUB_REPOSITORY', ''))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
