"""TEST-only CLI: sign in as owner A and build read-only postgame storage plan.

Requires genuine, separately supplied snapshot and final-stat JSON artifacts.
Never enables cloud writes; never prints bearer tokens or passwords.
"""
import argparse
import json
import os
from pathlib import Path

from phase3_authenticated_owner_pipeline import run as owner_run
from phase3_tracking_live_smoke import BASE, REPOSITORY, authenticate


def execute(snapshots, stats, output_dir, env=None, *, login=authenticate, pipeline=owner_run):
    env = os.environ if env is None else env
    if env.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise ValueError('Designated TEST repository required')
    if env.get('NFL_TEST_SUPABASE_URL', '').rstrip('/') != BASE:
        raise ValueError('Designated TEST Supabase URL required')
    key = env.get('NFL_TEST_SUPABASE_PUBLISHABLE_KEY', '')
    email = env.get('NFL_TEST_USER_A_EMAIL', '')
    password = env.get('NFL_TEST_USER_A_PASSWORD', '')
    if not all((key, email, password)):
        raise ValueError('TEST owner credentials required')
    if not all(Path(p).is_file() for p in (snapshots, stats)):
        raise ValueError('Real snapshot and final-stat files required')
    token, owner = login(email, password, key)
    if not token or not owner:
        raise ValueError('Invalid authenticated owner identity')
    result = pipeline(snapshots, stats, output_dir, owner, BASE, key, token, REPOSITORY)
    if result.get('database_writes') != 0 or result.get('cloud_writes_enabled') is not False:
        raise ValueError('Unsafe result: cloud writes must remain disabled')
    return {k: v for k, v in result.items() if k not in ('access_token', 'token', 'password')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshots', required=True)
    parser.add_argument('--stats', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.snapshots, args.stats, args.output_dir), sort_keys=True))


if __name__ == '__main__':
    main()
