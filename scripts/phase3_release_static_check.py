#!/usr/bin/env python3
"""Offline release smoke check. No network, secrets, or cloud writes."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def check(root=ROOT):
    page = root / 'index.html'
    if not page.is_file():
        raise RuntimeError('index.html missing')
    html = page.read_text(encoding='utf-8')
    scripts = re.findall(r'<script\b([^>]*)>(.*?)</script\s*>', html, re.I | re.S)
    inline = [body for attrs, body in scripts if not re.search(r'\bsrc\s*=', attrs, re.I) and body.strip()]
    if not inline:
        raise RuntimeError('No inline application scripts found')
    with tempfile.TemporaryDirectory() as tmp:
        for i, source in enumerate(inline, 1):
            path = Path(tmp) / f'inline-{i}.js'
            path.write_text(source, encoding='utf-8')
            result = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(f'Inline script {i} syntax failed: {result.stderr.strip()}')
    return {'mode':'OFFLINE_READ_ONLY', 'inline_scripts_checked':len(inline), 'cloud_writes_performed':0, 'live_validation_performed':False}

if __name__ == '__main__':
    try:
        print(json.dumps(check(), indent=2))
    except (RuntimeError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
