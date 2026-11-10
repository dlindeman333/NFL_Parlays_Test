#!/usr/bin/env python3
"""Read-only ingestion of an explicitly configured HTTPS injury observations feed.

Requires a feed that already exports the Phase 3 observation schema. A generic
scoreboard is not an injury feed. No completeness claim or cloud write is made.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from phase3_injury_records import validate_injury_records

MAX_BYTES = 5_000_000


def ingest(url, allowed_host, *, fetch=urlopen, now=None):
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ValueError('a clean HTTPS feed URL is required')
    if not allowed_host or parts.hostname.lower() != allowed_host.lower():
        raise ValueError('feed host is not allowlisted')
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'NFL-Phase3-TEST-Injury-ReadOnly/1.0'})
    with fetch(request, timeout=20) as response:
        final = urlsplit(response.geturl())
        if final.scheme != 'https' or final.hostname != parts.hostname:
            raise ValueError('feed redirect changed the trusted origin')
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('injury feed exceeds maximum size')
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError('expected an array of injury observations')
    records = validate_injury_records(payload, now=now)
    return {'mode': 'READ_ONLY_INGESTION', 'source_url': url,
            'sha256': hashlib.sha256(raw).hexdigest(), 'validated_records': len(records),
            'injury_records_written': 0, 'injury_sync_complete': False,
            'coverage_independently_verified': False, 'records': records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--allowed-host', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = ingest(args.url, args.allowed_host)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Validated {report['validated_records']} injury observations; 0 cloud writes")


if __name__ == '__main__':
    main()
