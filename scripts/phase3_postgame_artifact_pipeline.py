"""Generate a fail-closed postgame readiness report and optional offline grade export.

No credentials, network requests, or database writes are used.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path
from phase3_postgame_grading_gate import run
from phase3_grade_export import build_export


def produce(snapshots=None, stats=None, output_dir='.'):
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    # Remove any prior success artifact before starting a new evaluation.
    export_path = destination / 'phase3-grade-export.json'
    export_path.unlink(missing_ok=True)
    readiness = run(snapshots, stats)
    (destination / 'postgame-grading-readiness.json').write_text(
        json.dumps(readiness, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    if not readiness['ready']:
        return {'ready': False, 'exported_rows': 0, 'database_writes': 0}
    artifact = build_export(snapshots, stats)
    if not artifact['ready'] or artifact['database_writes'] != 0:
        raise ValueError('Grade export violated offline contract')
    # Publish a complete validated export atomically. A crash must not expose
    # a truncated success artifact to downstream automation.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=destination, prefix='.grade-export-',
                                         suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(artifact, handle, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, export_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'ready': True, 'exported_rows': len(artifact['rows']), 'database_writes': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshots')
    parser.add_argument('--stats')
    parser.add_argument('--output-dir', default='.')
    args = parser.parse_args()
    print(json.dumps(produce(args.snapshots, args.stats, args.output_dir)))


if __name__ == '__main__':
    main()
