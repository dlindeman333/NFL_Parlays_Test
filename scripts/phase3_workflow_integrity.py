#!/usr/bin/env python3
"""Offline integrity report for TEST GitHub Actions Python entrypoints.

Read-only: never invokes workflows, credentials, or network requests.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'
PATTERN = re.compile(r'\bpython(?:3(?:\.\d+)?)?\s+(scripts/[\w./-]+\.py)\b')


def audit(root=ROOT):
    workflows = root / '.github' / 'workflows'
    missing, present = [], []
    for workflow in sorted(workflows.glob('*.yml')):
        content = workflow.read_text(encoding='utf-8')
        for relative in sorted(set(PATTERN.findall(content))):
            entry = {'workflow': workflow.name, 'script': relative}
            (present if (root / relative).is_file() else missing).append(entry)
    return {'workflow_count': len(list(workflows.glob('*.yml'))),
            'entrypoints_checked': len(present) + len(missing),
            'missing_count': len(missing), 'missing': missing, 'present': present}


def main():
    report = audit()
    output = ROOT / 'phase3-integrity-report.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Workflow entrypoints: {report['entrypoints_checked']}; missing: {report['missing_count']}")
    for entry in report['missing']:
        print(f"MISSING {entry['workflow']}: {entry['script']}")
    # Informational by design: legacy workflows are not part of the release gate.


if __name__ == '__main__':
    main()
