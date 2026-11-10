"""Verify external injury-feed coverage attestations before generating a read-only plan.

This is an integrity/coverage *claim* check, not independent proof that a
publisher supplied every NFL player. It cannot authorize cloud writes.
"""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def verify_feed_evidence(observations_path, evidence_path, *, now=None):
    raw = Path(observations_path).read_bytes()
    evidence = json.loads(Path(evidence_path).read_text(encoding='utf-8'))
    if not isinstance(evidence, dict):
        raise ValueError('coverage evidence must be an object')
    if evidence.get('sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('coverage evidence does not match observation bytes')
    if evidence.get('coverage') != 'FULL_NFL_INJURY_FEED':
        raise ValueError('full NFL injury-feed coverage not attested')
    if evidence.get('independently_verified') is not True:
        raise ValueError('independent coverage verification absent')
    for field in ('source_url', 'verified_by', 'season', 'week'):
        if not evidence.get(field):
            raise ValueError(f'missing coverage evidence: {field}')
    if not isinstance(evidence['season'], int) or not isinstance(evidence['week'], int) or not 1 <= evidence['week'] <= 22:
        raise ValueError('invalid season/week coverage')
    try:
        observed = datetime.fromisoformat(evidence['verified_at'].replace('Z', '+00:00'))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('invalid verification time') from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('verification time must be timezone aware')
    now = now or datetime.now(timezone.utc)
    if observed > now + timedelta(minutes=5) or now - observed > timedelta(hours=24):
        raise ValueError('coverage verification is stale or future-dated')
    records = json.loads(raw)
    if not isinstance(records, list) or not records:
        raise ValueError('coverage evidence refers to empty or invalid feed')
    return {'source_url': evidence['source_url'], 'verified_at': observed.isoformat(),
            'verified_by': evidence['verified_by'], 'sha256': evidence['sha256'],
            'season': evidence['season'], 'week': evidence['week'],
            'independently_verified_claimed': True, 'cloud_writes_enabled': False}
