#!/usr/bin/env python3
"""Offline, fail-closed Phase 3 TEST release-readiness inventory. No network/writes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_WORKFLOWS = (
    'nfl-phase3-consolidated-test-gate.yml',
    'nfl-phase3-prediction-capture-link-readonly.yml',
    'nfl-phase3-postgame-readiness.yml',
    'nfl-phase3-weekly-injury-readiness.yml',
    'nfl-phase3-api-isolation.yml',
)
REQUIRED_SCRIPTS = (
    'phase3_test_boundary.py', 'phase3_prediction_capture_link.py',
    'phase3_postgame_grading_gate.py', 'phase3_weekly_injury_preview.py',
    'nfl_phase3_api_isolation.py',
)


def assess(root=ROOT):
    missing = [str(p) for p in
               [*(Path('.github/workflows') / x for x in CORE_WORKFLOWS),
                *(Path('scripts') / x for x in REQUIRED_SCRIPTS)]
               if not (root / p).is_file()]
    blockers = [
        'trusted_upstream_publication_timing_unverified',
        'automated_verified_pregame_storage_not_implemented',
        'automatic_cloud_grading_persistence_not_implemented',
        'actual_weekly_injury_synchronization_not_implemented',
        'live_test_cloud_and_cross_device_acceptance_not_completed',
    ]
    if missing:
        blockers.append('required_release_components_missing')
    return {'environment': 'TEST', 'ready_for_live_release': False,
            'cloud_writes_enabled': False, 'production_authorized': False,
            'core_files_missing': missing, 'release_blockers': blockers}


def main():
    report = assess()
    print(json.dumps(report, indent=2))
    # This inventory reports blockers without failing the offline regression workflow.


if __name__ == '__main__':
    main()
