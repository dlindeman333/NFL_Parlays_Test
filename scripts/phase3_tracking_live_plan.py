"""TEST-only authenticated read + offline grading persistence plan. NEVER writes to Supabase."""
import argparse
import json
import os
from pathlib import Path

from phase3_tracking_live_preflight import preflight
from phase3_tracking_persistence_plan import plan


def build_live_plan(grade_export, base_url, key, token, expected_user, repository, opener=None):
    """Use a verified owner-only paginated read as input to the offline planner."""
    # Validate the full read and ownership boundary before exposing records to planner.
    # The preflight collects records only through this callback, never logging credentials.
    rows = []
    kwargs = {'record_sink': rows.append}
    if opener is not None:
        kwargs['opener'] = opener
    audit = preflight(base_url, key, token, expected_user, repository, **kwargs)
    result = plan(grade_export, rows, expected_user)
    if result['conflicts_blocked']:
        result['activation_allowed'] = False
    result['live_read_preflight'] = audit
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grade-export', required=True)
    parser.add_argument('--expected-user', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    export = json.loads(Path(args.grade_export).read_text())
    result = build_live_plan(export, os.getenv('NFL_TEST_SUPABASE_URL', ''),
                             os.getenv('NFL_TEST_SUPABASE_PUBLISHABLE_KEY', ''),
                             os.getenv('NFL_TEST_USER_ACCESS_TOKEN', ''),
                             args.expected_user, os.getenv('GITHUB_REPOSITORY', ''))
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'mode': result['mode'], 'proposed_count': len(result['proposed_inserts']),
                      'conflicts_count': len(result['conflicts_blocked']), 'database_writes': 0}))


if __name__ == '__main__':
    main()
