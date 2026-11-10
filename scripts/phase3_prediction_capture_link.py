#!/usr/bin/env python3
"""Read-only cross-artifact linkage: capture evidence versus independent prediction preview.

This check never certifies upstream publication time or enables database writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
from phase3_snapshot_release_gate import timestamp


def assess(capture_dir, prediction_path):
    reasons = []
    try:
        capture = json.loads((capture_dir / 'capture_manifest.json').read_text(encoding='utf-8'))
        source = (capture_dir / 'source_stats.csv').read_bytes()
    except (OSError, ValueError, TypeError):
        return {'status': 'BLOCKED', 'linkage': 'FAIL', 'reasons': ['capture_unavailable'],
                'independent_prediction_compared': False, 'cloud_writes': 0, 'certified_snapshots': 0}
    try:
        preview = json.loads(prediction_path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return {'status': 'BLOCKED', 'linkage': 'FAIL', 'reasons': ['prediction_preview_unavailable'],
                'independent_prediction_compared': False, 'cloud_writes': 0, 'certified_snapshots': 0}
    digest = hashlib.sha256(source).hexdigest()
    if not source or capture.get('raw_csv_sha256') != digest or capture.get('raw_csv_size_bytes') != len(source):
        reasons.append('capture_content_mismatch')
    if preview.get('source_csv_sha256') != digest:
        reasons.append('prediction_source_mismatch')
    started = timestamp(capture.get('capture_started_utc'))
    ended = timestamp(capture.get('capture_completed_utc'))
    predicted = timestamp(preview.get('run_at_utc'))
    if not started or not ended or not predicted or not started <= ended <= predicted:
        reasons.append('invalid_capture_prediction_order')
    if capture.get('season') != preview.get('season') or capture.get('week') != preview.get('week'):
        reasons.append('season_week_mismatch')
    if preview.get('mode') != 'READ_ONLY' or preview.get('database_writes') != 0:
        reasons.append('unexpected_preview_mode')
    # A preview must explicitly remain unverified and contain no persisted outcomes.
    # This prevents a mislabeled or accidentally write-enabled producer from passing.
    if (preview.get('readiness') != 'BLOCKED_FOR_AUTOMATED_SNAPSHOTS'
            or preview.get('point_in_time_verified') is not False
            or preview.get('prediction_snapshots_created') != 0
            or preview.get('grades_created') != 0):
        reasons.append('preview_certification_safety_violation')
    blockers = preview.get('blocking_reasons')
    if not isinstance(blockers, list) or not all(isinstance(x, str) for x in blockers) or not blockers:
        reasons.append('missing_preview_provenance_blockers')
    # Integrity and ordering alone never establish historical upstream publication time.
    reasons.append('upstream_publication_provenance_unverified')
    return {'status': 'BLOCKED', 'linkage': 'PASS' if len(reasons) == 1 else 'FAIL',
            'reasons': sorted(set(reasons)), 'independent_prediction_compared': True,
            'cloud_writes': 0, 'certified_snapshots': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture-dir', type=Path, required=True)
    parser.add_argument('--prediction-preview', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('phase3-prediction-capture-link.json'))
    args = parser.parse_args()
    result = assess(args.capture_dir, args.prediction_preview)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
