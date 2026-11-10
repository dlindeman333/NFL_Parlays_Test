"""Offline verification of proposed prediction-history inserts; never writes data."""
import argparse
import hashlib
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def verify(plan, expected_user_id):
    if not isinstance(plan, dict) or plan.get('mode') != 'TRACKING_PERSISTENCE_PLAN_ONLY':
        raise ValueError('Unexpected persistence plan format')
    if plan.get('database_writes') != 0 or plan.get('activation_allowed') is not False:
        raise ValueError('Persistence plan must remain locked and read-only')
    rows = plan.get('proposed_inserts')
    if not isinstance(rows, list) or not isinstance(expected_user_id, str) or not expected_user_id.strip():
        raise ValueError('Missing user identity or proposed inserts')
    if plan.get('conflicts_blocked'):
        raise ValueError('Unresolved tracking conflicts prevent activation')
    if not isinstance(plan.get('existing_preserved'), list):
        raise ValueError('Missing preserved-record summary')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'user_id', 'tracking_id', 'payload'}:
            raise ValueError('Invalid insert shape')
        key = row['tracking_id']
        payload = row['payload']
        if row['user_id'] != expected_user_id or not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key) or key in seen:
            raise ValueError('Wrong owner or duplicate/invalid tracking ID')
        if not isinstance(payload, dict) or payload.get('tracking_id') != key or payload.get('grade') not in ('HIT', 'MISS', 'PUSH') or payload.get('provenance_status') != 'VERIFIED_PREGAME':
            raise ValueError('Invalid prediction grade or provenance')
        seen.add(key)
    if seen.intersection(plan['existing_preserved']):
        raise ValueError('Existing records cannot be reinserted')
    digest = hashlib.sha256(canonical(rows).encode()).hexdigest()
    if plan.get('proposal_sha256') != digest:
        raise ValueError('Proposal fingerprint mismatch')
    return {'verified': True, 'proposed_count': len(rows), 'database_writes': 0, 'activation_allowed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--user-id', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(Path(args.plan).read_text()), args.user_id)))


if __name__ == '__main__':
    main()
