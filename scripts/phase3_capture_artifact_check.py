#!/usr/bin/env python3
"""Fail-closed, offline integrity check for generated TEST forecast artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
from phase3_forecast_snapshot import canonical


def check_directory(directory):
    paths = sorted(Path(directory).glob('forecast-*.json'))
    if len(paths) != 1:
        raise ValueError('expected_exactly_one_forecast_artifact')
    artifact = json.loads(paths[0].read_text(encoding='utf-8'))
    payload = artifact['payload']
    digest = hashlib.sha256(canonical(payload)).hexdigest()
    if artifact.get('payload_sha256') != digest or digest[:16] not in paths[0].name:
        raise ValueError('forecast_integrity_mismatch')
    rows = payload['forecasts']
    keys = [row['logical_key'] for row in rows]
    if not rows or len(keys) != len(set(keys)) or len(rows) != payload['forecast_count']:
        raise ValueError('forecast_population_mismatch')
    if payload.get('classification') != 'MODEL_BASELINE_NOT_SPORTSBOOK_PICK':
        raise ValueError('unexpected_forecast_classification')
    if payload.get('database_writes') != 0 or payload.get('betting_picks_created') != 0:
        raise ValueError('unexpected_write_or_pick_claim')
    if payload.get('provenance_status') != 'UPSTREAM_PUBLICATION_NOT_INDEPENDENTLY_VERIFIED':
        raise ValueError('unsupported_provenance_claim')
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', default='phase3-forecast-output')
    args = parser.parse_args()
    print(f'Validated {check_directory(args.directory)} forecast records; no database writes')


if __name__ == '__main__':
    main()
