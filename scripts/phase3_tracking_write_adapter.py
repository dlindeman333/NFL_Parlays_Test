"""TEST-only owner-scoped insert adapter; disabled by default.

This module does not schedule writes. Callers must obtain separate authorization
before supplying an enabled activation flag and a user access token.
"""
import hashlib
import json
import urllib.parse
import urllib.request

from phase3_tracking_live_preflight import preflight
from phase3_tracking_persistence_plan import _canonical


class PartialTrackingWriteError(RuntimeError):
    """A batch failed after some inserts; do not blindly retry the entire batch."""

    def __init__(self, confirmed_ids, attempted_id):
        self.confirmed_ids = tuple(confirmed_ids)
        self.attempted_id = attempted_id
        super().__init__(
            'Tracking batch stopped after %d confirmed inserts; '
            'reconcile cloud history before retrying' % len(self.confirmed_ids)
        )


def prepare_write(plan, user_id):
    """Validate a previously generated plan without granting write permission."""
    if plan.get('mode') != 'TRACKING_PERSISTENCE_PLAN_ONLY' or plan.get('database_writes') != 0:
        raise ValueError('Only an offline tracking persistence plan is supported')
    if plan.get('activation_allowed') is not False:
        raise ValueError('Plan must remain locked')
    rows = plan.get('proposed_inserts')
    if not isinstance(rows, list) or plan.get('conflicts_blocked'):
        raise ValueError('Invalid or conflicting write plan')
    if hashlib.sha256(_canonical(rows).encode()).hexdigest() != plan.get('proposal_sha256'):
        raise ValueError('Plan integrity verification failed')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('user_id') != user_id:
            raise ValueError('Plan owner mismatch')
        tracking_id = row.get('tracking_id')
        if not isinstance(tracking_id, str) or len(tracking_id) != 64 or any(c not in '0123456789abcdef' for c in tracking_id) or tracking_id in ids:
            raise ValueError('Invalid tracking ID')
        ids.add(tracking_id)
        payload = row.get('payload')
        if (not isinstance(payload, dict) or payload.get('provenance_status') != 'VERIFIED_PREGAME'
                or payload.get('grade') not in ('HIT', 'MISS', 'PUSH')
                or payload.get('synthetic') is True or payload.get('exclude_from_grading') is True
                or payload.get('exclude_from_accuracy') is True or payload.get('record_type') == 'RLS_SECURITY_TEST'):
            raise ValueError('Unverified grade payload')
    return rows


def apply_plan(plan, user_id, base_url, key, token, repository, *, enabled=False, opener=urllib.request.urlopen):
    """Fail closed unless explicitly enabled; insert-only with no upsert or overwrite.

    Each row uses an insert with returning=minimal. A uniqueness conflict stops
    execution rather than replacing an existing prediction record.
    """
    rows = prepare_write(plan, user_id)
    if not enabled:
        return {'mode': 'LOCKED', 'database_writes': 0, 'proposed_count': len(rows)}
    if not rows:
        return {'mode': 'TEST_OWNER_NOOP', 'database_writes': 0, 'proposed_count': 0}
    # Recheck the authenticated user and TEST project immediately before writing.
    # Refresh the full owner-visible history immediately before inserting.
    # A stale plan must not silently collide with records saved since planning.
    existing_ids = set()
    def collect_existing(record):
        existing_ids.add(record['tracking_id'])
    verification = preflight(base_url, key, token, user_id, repository,
                             opener=opener, record_sink=collect_existing)
    if (not isinstance(verification, dict)
            or verification.get('authenticated_owner_verified') is not True
            or verification.get('mode') != 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT'
            or verification.get('database_writes') != 0
            or verification.get('visible_tracking_records') != len(existing_ids)):
        raise ValueError('Authenticated read-only preflight evidence is incomplete')
    if existing_ids.intersection(row['tracking_id'] for row in rows):
        raise ValueError('Tracking plan is stale: proposed ID already exists')
    origin = 'https://' + urllib.parse.urlsplit(base_url).hostname
    endpoint = origin + '/rest/v1/nfl_user_prediction_tracking'
    confirmed_ids = []
    for row in rows:
        request = urllib.request.Request(endpoint,
            data=json.dumps(row, allow_nan=False).encode('utf-8'),
            headers={'apikey': key, 'Authorization': 'Bearer ' + token,
                     'Content-Type': 'application/json', 'Prefer': 'return=minimal'},
            method='POST')
        try:
            with opener(request, timeout=15) as response:
                if response.status not in (201, 204):
                    raise ValueError('Supabase insert did not return success')
        except Exception as exc:
            # Even the attempted row may have committed before a network failure.
            # A fresh owner-scoped read is required before any retry.
            raise PartialTrackingWriteError(confirmed_ids, row['tracking_id']) from exc
        confirmed_ids.append(row['tracking_id'])
    return {'mode': 'TEST_OWNER_INSERT', 'database_writes': len(confirmed_ids)}


def reconcile_after_failure(plan, user_id, base_url, key, token, repository,
                            *, opener=urllib.request.urlopen):
    """Read-only recovery after an uncertain insert outcome.

    Never retries inserts automatically. Conflicting or missing records require
    an explicit new plan, so a timeout cannot silently overwrite history.
    """
    rows = prepare_write(plan, user_id)
    current = {}
    def collect(record):
        current[record['tracking_id']] = record
    verification = preflight(base_url, key, token, user_id, repository,
                             opener=opener, record_sink=collect)
    if (not isinstance(verification, dict)
            or verification.get('mode') != 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT'
            or verification.get('authenticated_owner_verified') is not True
            or verification.get('database_writes') != 0
            or verification.get('visible_tracking_records') != len(current)):
        raise ValueError('Recovery preflight evidence is incomplete')
    confirmed, missing, conflicting = [], [], []
    for row in rows:
        saved = current.get(row['tracking_id'])
        if saved is None:
            missing.append(row['tracking_id'])
        elif saved.get('user_id') == user_id and saved.get('payload') == row['payload']:
            confirmed.append(row['tracking_id'])
        else:
            conflicting.append(row['tracking_id'])
    return {'mode': 'TEST_OWNER_READ_ONLY_RECONCILIATION',
            'database_writes': 0, 'confirmed_ids': confirmed,
            'missing_ids': missing, 'conflicting_ids': conflicting,
            'safe_to_retry_automatically': False}
