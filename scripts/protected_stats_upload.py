"""Phase 3B: guarded update of only nfl_stat_exports season=2026.
Default preview; upload requires explicit workflow input and durable artifact step first.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from upload_stats import inspect

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'backup_artifact'
CSV = ROOT / 'nfl_player_stats.csv'


def get_current(url, key):
    endpoint = url + '/rest/v1/nfl_stat_exports?select=season,generated_at,record_count,csv_text&season=eq.2026'
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key, 'Accept': 'application/json'}
    with urlopen(Request(endpoint, headers=headers), timeout=120) as response:
        rows = json.load(response)
    if len(rows) != 1:
        raise ValueError('Expected exactly one existing 2026 record')
    return rows[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['preview', 'upload'], default='preview')
    parser.add_argument('--confirm', default='')
    args = parser.parse_args()
    if args.mode == 'upload' and args.confirm != 'UPLOAD_2026_STATS':
        raise ValueError('Upload blocked: exact typed confirmation required')
    if args.mode == 'upload' and os.environ.get('BACKUP_ARTIFACT_UPLOADED') != 'true':
        raise ValueError('Upload blocked: backup artifact step did not complete')
    url = os.environ['SUPABASE_URL'].rstrip('/')
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    if not url.startswith('https://'):
        raise ValueError('SUPABASE_URL must use HTTPS')
    manifest = json.loads((BASE / 'manifest.json').read_text(encoding='utf-8'))
    old = json.loads((BASE / 'nfl_stat_exports_2026_record.json').read_text(encoding='utf-8'))
    old_bytes = (BASE / 'nfl_stat_exports_2026.csv').read_bytes()
    if hashlib.sha256(old_bytes).hexdigest() != manifest['csv_sha256']:
        raise ValueError('Stored backup CSV checksum mismatch')
    if old_bytes != old['csv_text'].encode('utf-8'):
        raise ValueError('Backup CSV differs from original database record')
    old_stats = inspect(old['csv_text'])
    if old['season'] != 2026 or old['record_count'] != old_stats['rows'] or old_stats['sha256'] != manifest['csv_sha256']:
        raise ValueError('Backup metadata mismatch')
    new_text = CSV.read_text(encoding='utf-8-sig')
    new = inspect(new_text)
    if new['season'] != 2026:
        raise ValueError('Wrong season')
    if new['rows'] < old_stats['rows'] or new['completed'] < old_stats['completed']:
        raise ValueError('BLOCKED: export would reduce total or completed records')
    if not set(old_stats['fields']).issubset(new['fields']):
        raise ValueError('BLOCKED: export would remove existing columns')
    # Fail closed if another process has updated the database since the backup.
    current = get_current(url, key)
    if current != old:
        raise ValueError('BLOCKED: database changed since backup; rerun from the beginning')
    print(f"Backup verified: rows={old_stats['rows']}, completed={old_stats['completed']}, columns={old_stats['columns']}")
    print(f"New export: rows={new['rows']}, completed={new['completed']}, columns={new['columns']}")
    if new['sha256'] == old_stats['sha256']:
        print('NO UPDATE NEEDED: exports are identical. No database write performed.')
        return
    if args.mode == 'preview':
        print('PREVIEW PASSED: changes detected, but no database write performed.')
        return
    # Optimistic concurrency check on the original generated_at; no upsert/insertion.
    timestamp = old.get('generated_at')
    if not timestamp:
        raise ValueError('Existing record has no generated_at; cannot safely update')
    filter_value = quote(str(timestamp), safe='')
    endpoint = url + '/rest/v1/nfl_stat_exports?season=eq.2026&generated_at=eq.' + filter_value
    payload = {'generated_at': datetime.now(timezone.utc).isoformat(),
               'record_count': new['rows'], 'csv_text': new_text}
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key,
               'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    req = Request(endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers, method='PATCH')
    with urlopen(req, timeout=120) as response:
        updated = json.load(response)
    if len(updated) != 1:
        raise ValueError('BLOCKED: update did not affect exactly one record; check DB and restore plan')
    verified = get_current(url, key)
    if (verified.get('record_count') != new['rows'] or
            hashlib.sha256(verified['csv_text'].encode('utf-8')).hexdigest() != new['sha256']):
        raise ValueError('POST-UPLOAD VERIFICATION FAILED. Keep backup; investigate before retrying')
    print('UPLOAD VERIFIED: 2026 statistics updated and database checksum matches new export.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, HTTPError, KeyError) as exc:
        raise SystemExit(f'PROTECTED WORKFLOW STOPPED: {exc}') from exc
