"""Fail-closed validation for externally supplied NFL injury observations.

This module does not fetch a feed or perform database writes. Only source-stamped
observations may pass; unknown statuses are never silently mapped to healthy.
"""
from datetime import datetime, timezone, timedelta

STATUSES = {'OUT', 'DOUBTFUL', 'QUESTIONABLE', 'PROBABLE', 'ACTIVE', 'INACTIVE', 'INJURED_RESERVE', 'PUP', 'NFI'}


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError('observation timestamp missing')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid observation timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('observation timestamp must include timezone')
    return parsed.astimezone(timezone.utc)


def validate_injury_records(records, *, now=None, max_age=timedelta(days=7)):
    """Return normalized records; reject entire batch if any record is unsafe."""
    if not isinstance(records, list):
        raise ValueError('injury observations must be a list')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must include timezone')
    now = now.astimezone(timezone.utc)
    seen = set()
    normalized = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f'record {index}: not an object')
        fields = {}
        for key in ('player_id', 'team', 'source'):
            value = record.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'record {index}: missing {key}')
            fields[key] = value.strip()
        status = record.get('status')
        if not isinstance(status, str) or status.strip().upper() not in STATUSES:
            raise ValueError(f'record {index}: unknown injury status')
        fields['status'] = status.strip().upper()
        observed = _timestamp(record.get('observed_at'))
        if observed > now + timedelta(minutes=5):
            raise ValueError(f'record {index}: future observation')
        if now - observed > max_age:
            raise ValueError(f'record {index}: stale observation')
        key = (fields['player_id'], fields['team'])
        if key in seen:
            raise ValueError(f'record {index}: duplicate player observation')
        seen.add(key)
        fields['observed_at'] = observed.isoformat()
        normalized.append(fields)
    return normalized
