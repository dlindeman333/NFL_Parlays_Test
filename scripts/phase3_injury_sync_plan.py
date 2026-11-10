"""Deterministic, read-only injury update planning.

Never infers ACTIVE from absence in a feed. An incomplete feed must not
clear prior injury statuses. This module does not connect to Supabase.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from phase3_injury_records import validate_injury_records, _timestamp, STATUSES


def build_sync_plan(observations, existing, *, now=None, feed_complete=False):
    """Return proposed upserts only; require explicit full-feed coverage evidence.

    `existing` is a list of previously validated records. No deletes are planned.
    """
    if not isinstance(feed_complete, bool) or not feed_complete:
        raise ValueError('full injury feed coverage not verified; sync blocked')
    if not isinstance(existing, list):
        raise ValueError('existing records must be a list')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must include timezone')
    now = now.astimezone(timezone.utc)
    current = validate_injury_records(observations, now=now)
    if not current:
        raise ValueError('empty injury feed cannot establish complete coverage')
    old = {}
    for record in existing:
        if not isinstance(record, dict):
            raise ValueError('existing injury record must be an object')
        player_id, team = record.get('player_id'), record.get('team')
        if not isinstance(player_id, str) or not player_id.strip() or not isinstance(team, str) or not team.strip():
            raise ValueError('invalid existing injury identity')
        # Reject noncanonical stored identities rather than silently creating a
        # second record for the same player with different whitespace.
        if player_id != player_id.strip() or team != team.strip():
            raise ValueError('noncanonical existing injury identity; sync blocked')
        key = (player_id, team)
        if key in old:
            raise ValueError('duplicate existing injury identity')
        if record.get('status') not in STATUSES or not isinstance(record.get('source'), str) or not record['source'].strip():
            raise ValueError('invalid existing injury status or source')
        try:
            prior_time = _timestamp(record.get('observed_at'))
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid existing observation timestamp') from exc
        if prior_time > now.astimezone(timezone.utc) + timedelta(minutes=5):
            raise ValueError('existing injury observation is future-dated; sync blocked')
        old[key] = record
    updates, unchanged, stale = [], 0, 0
    for record in current:
        key = (record['player_id'], record['team'])
        prior = old.get(key)
        if prior is not None:
            try:
                old_time = _timestamp(prior['observed_at'])
                new_time = _timestamp(record['observed_at'])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError('invalid existing observation timestamp') from exc
            if new_time < old_time:
                stale += 1
                continue
            if new_time == old_time and (prior.get('status') != record['status'] or prior.get('source') != record['source']):
                raise ValueError('conflicting injury observation at identical timestamp; sync blocked')
            if prior.get('status') == record['status'] and prior.get('source') == record['source'] and old_time == new_time:
                unchanged += 1
                continue
        updates.append(record)
    return {
        'mode': 'READ_ONLY_SYNC_PLAN', 'cloud_writes_enabled': False,
        'feed_coverage_verified_by_caller': True,
        'observations_received': len(current), 'proposed_upserts': updates,
        'proposed_deletes': [], 'unchanged': unchanged,
        'older_than_stored_skipped': stale,
        'previously_stored_not_in_feed_preserved': len(set(old) - {(r['player_id'], r['team']) for r in current}),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Offline injury sync plan, never writes')
    parser.add_argument('--observations', required=True)
    parser.add_argument('--existing', required=True)
    parser.add_argument('--feed-complete', action='store_true', help='Only when completeness independently verified')
    parser.add_argument('--output', default='phase3-injury-sync-plan.json')
    args = parser.parse_args()
    plan = build_sync_plan(json.loads(Path(args.observations).read_text()),
                           json.loads(Path(args.existing).read_text()), feed_complete=args.feed_complete)
    Path(args.output).write_text(json.dumps(plan, indent=2) + '\n')
    print(f"Read-only plan: {len(plan['proposed_upserts'])} proposed upserts, zero writes")


if __name__ == '__main__':
    main()
