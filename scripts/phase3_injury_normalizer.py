#!/usr/bin/env python3
"""Fail-closed injury record normalization for a future TEST-only sync.

Consumes an explicitly supplied source export, never fetches or writes cloud data.
No injury record is treated as current without an explicit observation timestamp.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

STATUSES = {'OUT', 'DOUBTFUL', 'QUESTIONABLE', 'PROBABLE', 'ACTIVE', 'INACTIVE', 'INJURED_RESERVE', 'PUP', 'UNKNOWN'}


def utc_timestamp(value):
    if not isinstance(value, str):
        raise ValueError('observation timestamp required')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid observation timestamp') from exc
    if dt.tzinfo is None:
        raise ValueError('observation timestamp must contain timezone')
    return dt.astimezone(timezone.utc)


def normalize(payload, now=None):
    if not isinstance(payload, dict) or not isinstance(payload.get('injuries'), list):
        raise ValueError('injuries array required')
    source = payload.get('source')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('source identifier required')
    observed = utc_timestamp(payload.get('observed_at'))
    now = now or datetime.now(timezone.utc)
    if observed > now:
        raise ValueError('future observation timestamp')
    if (now - observed).total_seconds() > 7 * 86400:
        raise ValueError('stale injury source; older than 7 days')
    seen, records = set(), []
    for item in payload['injuries']:
        if not isinstance(item, dict):
            raise ValueError('invalid injury record')
        player = item.get('player_id')
        team = item.get('team')
        status = item.get('status')
        if not isinstance(player, str) or not player.strip() or not isinstance(team, str) or not team.strip():
            raise ValueError('player_id and team required')
        if status not in STATUSES:
            raise ValueError('unrecognized injury status')
        key = (team.strip(), player.strip())
        if key in seen:
            raise ValueError('duplicate player injury record')
        seen.add(key)
        records.append({'team': key[0], 'player_id': key[1], 'status': status,
                        'observed_at': observed.isoformat(), 'source': source.strip()})
    return {'mode': 'VALIDATED_STAGING_NO_CLOUD_WRITES', 'source': source.strip(),
            'observed_at': observed.isoformat(), 'injury_records_validated': len(records),
            'injury_records_written': 0, 'injury_sync_complete': False, 'records': records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = normalize(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"Validated {result['injury_records_validated']} injury records; 0 cloud writes")


if __name__ == '__main__':
    main()
