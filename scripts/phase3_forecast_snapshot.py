#!/usr/bin/env python3
"""Offline, content-addressed pregame MODEL forecast artifact (never sportsbook picks).

No network or database writes. An artifact alone does not certify source provenance.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
from phase3d37l_serializer_dry_run import audit_candidates, parse_time

UTC = dt.timezone.utc

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

def create_forecast_artifact(manifest, candidates, source_bytes, now=None, lead_minutes=30):
    now = now or dt.datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError('capture_time_must_be_timezone_aware')
    now = now.astimezone(UTC)
    sha = hashlib.sha256(source_bytes).hexdigest()
    if sha != manifest.get('source_sha256'):
        raise ValueError('source_hash_mismatch')
    if len(candidates) != manifest.get('candidate_metrics'):
        raise ValueError('candidate_count_mismatch')
    if manifest.get('source_freshness_blocker'):
        raise ValueError('stale_source')
    if manifest.get('season') is None or manifest.get('week') is None:
        raise ValueError('missing_season_week')
    generated = parse_time(manifest.get('source_generated_at'))
    if generated is None or generated > now:
        raise ValueError('invalid_source_generated_at')
    accepted, plans, rejected = audit_candidates(manifest, candidates, now, minimum_lead_minutes=lead_minutes)
    if rejected or len(accepted) != len(candidates) or not accepted:
        raise ValueError(f'unsafe_forecast_candidates:{rejected}')
    rows = []
    for item in sorted(accepted, key=lambda x: x['logical_key']):
        if generated >= parse_time(item['kickoff_at']):
            raise ValueError('source_not_before_kickoff')
        rows.append(item)
    payload = {
        'schema': 'phase3_model_forecast_v1',
        'classification': 'MODEL_BASELINE_NOT_SPORTSBOOK_PICK',
        'season': manifest['season'], 'week': manifest['week'],
        'captured_at_utc': now.isoformat(),
        'source_generated_at': generated.isoformat(),
        'source_sha256': sha,
        'forecast_count': len(rows),
        'forecasts': rows,
        'provenance_status': 'UPSTREAM_PUBLICATION_NOT_INDEPENDENTLY_VERIFIED',
        'betting_picks_created': 0, 'database_writes': 0,
    }
    return {'payload': payload, 'payload_sha256': hashlib.sha256(canonical(payload)).hexdigest()}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', default='phase3d37h-output')
    ap.add_argument('--output-dir', default='phase3-forecast-output')
    args = ap.parse_args()
    src = pathlib.Path(args.input_dir)
    manifest = json.loads((src / 'manifest.json').read_text())
    candidates = json.loads((src / 'candidates.json').read_text())
    artifact = create_forecast_artifact(manifest, candidates, (src / 'source.csv').read_bytes())
    dest = pathlib.Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"forecast-{manifest['season']}-week{manifest['week']}-{artifact['payload_sha256'][:16]}.json"
    # Never overwrite a previously captured artifact.
    with path.open('x', encoding='utf-8') as f:
        json.dump(artifact, f, indent=2)
        f.write('\n')
    print(f"Created {path}; forecasts={artifact['payload']['forecast_count']}; cloud_writes=0")

if __name__ == '__main__':
    main()
