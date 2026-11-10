"""Offline postgame grade-to-owner-plan pipeline; no network or database writes."""
import argparse
import json
import os
import tempfile
from pathlib import Path

from phase3_postgame_artifact_pipeline import produce
from phase3_tracking_persistence_plan import plan
from phase3_tracking_write_adapter import prepare_write


def build(snapshots, stats, existing, user_id, output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    # Fail closed on reruns: never expose a successful plan from an older run.
    plan_path = output / 'phase3-owner-tracking-plan.json'
    plan_path.unlink(missing_ok=True)
    grade_path = output / 'phase3-grade-export.json'
    grade = produce(snapshots, stats, output)
    if not grade['ready']:
        return {'ready': False, 'database_writes': 0, 'reason': 'Postgame grading gate blocked'}
    export = json.loads(grade_path.read_text(encoding='utf-8'))
    try:
        records = json.loads(Path(existing).read_text(encoding='utf-8'))
        result = plan(export, records, user_id)
        if result['conflicts_blocked']:
            grade_path.unlink(missing_ok=True)
            return {'ready': False, 'database_writes': 0, 'reason': 'Conflicting existing tracking records'}
        rows = prepare_write(result, user_id)
        if len(rows) != len(result['proposed_inserts']):
            raise ValueError('Prepared rows do not match planned inserts')
    except Exception:
        # Do not leave a standalone success-looking grade artifact after
        # owner reconciliation fails. The pipeline must be rerun from source.
        grade_path.unlink(missing_ok=True)
        raise
    # Publish only a complete plan; an interrupted write must not leave a
    # truncated file that another job could mistake for a valid artifact.
    fd, temporary = tempfile.mkstemp(prefix='.phase3-owner-', suffix='.tmp', dir=output)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, plan_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'ready': True, 'proposed_count': len(rows),
            'existing_preserved': len(result['existing_preserved']), 'database_writes': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshots', required=True)
    p.add_argument('--stats', required=True)
    p.add_argument('--existing', required=True)
    p.add_argument('--user-id', required=True)
    p.add_argument('--output-dir', required=True)
    a = p.parse_args()
    print(json.dumps(build(a.snapshots, a.stats, a.existing, a.user_id, a.output_dir)))


if __name__ == '__main__':
    main()
