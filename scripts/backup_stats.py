"""Read-only backup of 2026 nfl_stat_exports from Supabase REST API."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

SEASON = 2026
DEST = Path('backup_artifact')

def main():
    url = os.environ['SUPABASE_URL'].rstrip('/')
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    if not url.startswith('https://'):
        raise SystemExit('SUPABASE_URL must use HTTPS')
    endpoint = f'{url}/rest/v1/nfl_stat_exports?select=season,generated_at,record_count,csv_text&season=eq.{SEASON}'
    req = Request(endpoint, headers={'apikey': key, 'Authorization': 'Bearer ' + key, 'Accept': 'application/json'}, method='GET')
    with urlopen(req, timeout=120) as response:
        rows = json.load(response)
    if len(rows) != 1:
        raise SystemExit(f'Expected exactly one 2026 record; found {len(rows)}. No backup created.')
    record = rows[0]
    csv_text = record.get('csv_text')
    if not isinstance(csv_text, str) or not csv_text:
        raise SystemExit('Missing or empty stored csv_text. No backup created.')
    if record.get('season') != SEASON:
        raise SystemExit('Unexpected season')
    reader = csv.DictReader(io.StringIO(csv_text))
    fields = reader.fieldnames or []
    if not fields or len(fields) != len(set(fields)):
        raise SystemExit('CSV header invalid')
    count = sum(1 for _ in reader)
    if count < 1000 or record.get('record_count') != count:
        raise SystemExit('Stored metadata does not match CSV row count')
    payload = csv_text.encode('utf-8')
    digest = hashlib.sha256(payload).hexdigest()
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'nfl_stat_exports_2026.csv').write_bytes(payload)
    (DEST / 'nfl_stat_exports_2026_record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = {'season': SEASON, 'generated_at': record.get('generated_at'), 'record_count': count, 'column_count': len(fields), 'csv_sha256': digest, 'csv_bytes': len(payload), 'source_table': 'nfl_stat_exports', 'read_only': True}
    (DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # Validate backup bytes before artifact upload.
    if hashlib.sha256((DEST / 'nfl_stat_exports_2026.csv').read_bytes()).hexdigest() != digest:
        raise SystemExit('Backup checksum verification failed')
    print(f'BACKUP VERIFIED: season={SEASON}, rows={count}, columns={len(fields)}, sha256={digest}')
    print('Files ready for GitHub artifact upload. No database writes were performed.')

if __name__ == '__main__':
    main()
