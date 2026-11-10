#!/usr/bin/env python3
"""Audit an actual capture artifact without claiming an authentic prediction preview."""
import argparse
import json
from pathlib import Path
from phase3_capture_evidence_audit import audit_evidence


def assess(capture_dir):
    try:
        manifest = json.loads((capture_dir / 'capture_manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        manifest = {}
    # These values come from the capture manifest, NOT an independent prediction.
    # The audit is therefore an integrity self-check only.
    source_reference = {
        'source_sha256': manifest.get('raw_csv_sha256'),
        'source_acquired_at_utc': manifest.get('capture_completed_utc'),
    }
    result = audit_evidence(capture_dir, source_reference)
    result['check_type'] = 'capture_artifact_integrity_only'
    result['prediction_preview_compared'] = False
    result['trusted_pregame_capture'] = False
    result['automatic_grading_enabled'] = False
    result['cloud_writes'] = 0
    result['authentic_snapshots_created'] = 0
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--capture-dir', type=Path, default=Path('phase3d37e-evidence'))
    p.add_argument('--output', type=Path, default=Path('phase3d37e-evidence/capture_readiness.json'))
    args = p.parse_args()
    result = assess(args.capture_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
