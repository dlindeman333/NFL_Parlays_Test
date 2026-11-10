"""Fail-closed offline plan for per-user prediction tracking persistence.

No network calls, credentials or writes. Existing records are never overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def plan(export, existing, user_id):
    if export.get('mode') != 'OFFLINE_GRADE_EXPORT' or export.get('ready') is not True or export.get('database_writes') != 0:
        raise ValueError('Only ready, offline grade exports are accepted')
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError('Authenticated user identity required')
    if not isinstance(export.get('rows'), list) or not isinstance(existing, list):
        raise ValueError('Rows must be arrays')
    known = {}
    for record in existing:
        if record.get('user_id') != user_id:
            raise ValueError('Existing rows must belong exclusively to requested user')
        key = record.get('tracking_id')
        if not isinstance(key, str) or not key or key in known:
            raise ValueError('Invalid or duplicate existing tracking ID')
        known[key] = record.get('payload')
    proposed, preserved, conflicts, seen = [], [], [], set()
    for row in export['rows']:
        key = row.get('tracking_id')
        if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key) or key in seen:
            raise ValueError('Invalid or duplicate export tracking ID')
        seen.add(key)
        if row.get('grade') not in ('HIT', 'MISS', 'PUSH') or row.get('provenance_status') != 'VERIFIED_PREGAME':
            raise ValueError('Export contains unverified or ungradeable rows')
        if row.get('synthetic') is True or row.get('exclude_from_grading') is True or row.get('exclude_from_accuracy') is True or row.get('record_type') == 'RLS_SECURITY_TEST':
            raise ValueError('Synthetic security-test records cannot enter prediction persistence')
        payload = dict(row)
        if key not in known:
            proposed.append({'user_id': user_id, 'tracking_id': key, 'payload': payload})
        elif _canonical(known[key]) == _canonical(payload):
            preserved.append(key)
        else:
            conflicts.append(key)
    digest = hashlib.sha256(_canonical(proposed).encode()).hexdigest()
    return {'mode': 'TRACKING_PERSISTENCE_PLAN_ONLY', 'database_writes': 0,
            'activation_allowed': False, 'proposed_inserts': proposed,
            'existing_preserved': preserved, 'conflicts_blocked': conflicts,
            'proposal_sha256': digest,
            'blockers': ['Live authenticated owner-write validation required',
                         'Trusted capture and immutable evidence required',
                         'Explicit TEST write unlock required']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--grade-export', required=True)
    p.add_argument('--existing', required=True, help='Read-only JSON array of existing records for this user')
    p.add_argument('--user-id', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result = plan(json.loads(Path(a.grade_export).read_text()),
                  json.loads(Path(a.existing).read_text()), a.user_id)
    Path(a.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'proposed': len(result['proposed_inserts']), 'conflicts': len(result['conflicts_blocked']), 'database_writes': 0}))


if __name__ == '__main__':
    main()
