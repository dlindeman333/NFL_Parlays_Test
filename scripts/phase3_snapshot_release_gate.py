#!/usr/bin/env python3
"""Offline, fail-closed provenance gate for future pregame writers. Never writes data."""
import argparse
import datetime as dt
import json
from pathlib import Path

UTC = dt.timezone.utc

def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except ValueError:
        return None

def audit(manifest, candidates, now=None):
    now = now or dt.datetime.now(UTC)
    blockers = []
    if manifest.get('mode') != 'READ_ONLY_FULL_POPULATION_PREVIEW':
        blockers.append('unrecognized_manifest_mode')
    acquired = timestamp(manifest.get('source_acquired_at_utc'))
    generated = timestamp(manifest.get('source_generated_at'))
    if not acquired or not generated or generated > acquired or acquired > now + dt.timedelta(minutes=5):
        blockers.append('unverified_source_timing')
    if manifest.get('source_freshness_blocker'):
        blockers.append('source_stale')
    if manifest.get('candidate_metrics') != len(candidates):
        blockers.append('candidate_count_mismatch')
    if not candidates:
        blockers.append('no_candidates')
    if not isinstance(manifest.get('source_sha256'), str) or len(manifest['source_sha256']) != 64:
        blockers.append('invalid_source_fingerprint')
    seen = set()
    for item in candidates:
        key = item.get('logical_key')
        kickoff = timestamp(item.get('kickoff_at'))
        if not isinstance(key, str) or not key or key in seen:
            blockers.append('invalid_or_duplicate_candidate_key')
        seen.add(key)
        if not kickoff or kickoff <= now + dt.timedelta(minutes=15):
            blockers.append('kickoff_not_safely_ahead')
        if not generated or not kickoff or generated >= kickoff:
            blockers.append('source_not_before_kickoff')
        if item.get('source_sha256') != manifest.get('source_sha256'):
            blockers.append('candidate_source_mismatch')
    # These cannot be proven from the current manifest and must not be inferred.
    blockers += ['upstream_row_publication_times_unverified',
                 'historical_roster_provenance_unverified',
                 'prediction_schema_and_calibration_unverified',
                 'explicit_cloud_write_authorization_absent']
    return {'mode':'READ_ONLY_RELEASE_GATE','readiness':'BLOCKED',
            'blocking_reasons':sorted(set(blockers)), 'candidate_count':len(candidates),
            'cloud_writes':0,'authentic_snapshots_created':0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input-dir', default='phase3d37h-output')
    p.add_argument('--output', default='phase3-snapshot-release-gate.json')
    args=p.parse_args()
    src=Path(args.input_dir)
    result=audit(json.loads((src/'manifest.json').read_text()),
                 json.loads((src/'candidates.json').read_text()))
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':
    main()
