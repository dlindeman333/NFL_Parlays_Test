#!/usr/bin/env python3
"""Offline evidence-chain audit. Never authorizes historical pregame claims or cloud writes."""
import argparse
import hashlib
import json
from pathlib import Path
from phase3_snapshot_release_gate import timestamp


def audit_evidence(capture_dir, preview_manifest):
    problems = []
    try:
        capture = json.loads((capture_dir / 'capture_manifest.json').read_text(encoding='utf-8'))
        raw = (capture_dir / 'source_stats.csv').read_bytes()
    except (OSError, ValueError, TypeError):
        return {'status': 'BLOCKED', 'reasons': ['capture_evidence_unavailable'], 'cloud_writes': 0}
    digest = hashlib.sha256(raw).hexdigest()
    if not raw or digest != capture.get('raw_csv_sha256') or len(raw) != capture.get('raw_csv_size_bytes'):
        problems.append('capture_hash_or_size_mismatch')
    start = timestamp(capture.get('capture_started_utc'))
    end = timestamp(capture.get('capture_completed_utc'))
    if not start or not end or start > end:
        problems.append('invalid_capture_clock')
    acquired = timestamp(preview_manifest.get('source_acquired_at_utc'))
    if not acquired or not start or not end or not start <= acquired <= end:
        problems.append('preview_outside_capture_window')
    if preview_manifest.get('source_sha256') != digest:
        problems.append('preview_source_hash_mismatch')
    if capture.get('historical_point_in_time_verified') is not False:
        problems.append('capture_provenance_flag_unexpected')
    # Even a perfect file/hash match cannot prove the source was published before kickoff.
    problems.append('upstream_publication_provenance_unverified')
    return {'status': 'BLOCKED', 'evidence_integrity': 'PASS' if len(problems) == 1 else 'FAIL',
            'reasons': sorted(set(problems)), 'cloud_writes': 0, 'authentic_snapshots_created': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture-dir', type=Path, required=True)
    parser.add_argument('--preview-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('phase3-capture-evidence-audit.json'))
    args = parser.parse_args()
    try:
        preview = json.loads(args.preview_manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        preview = {}
    result = audit_evidence(args.capture_dir, preview)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
