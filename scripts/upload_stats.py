"""Safe Phase 3A CSV compare / opt-in upload. Default mode never writes."""
import argparse
import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / 'nfl_player_stats.csv'
REQUIRED = {'season', 'week', 'game_status', 'player_id', 'team', 'pass_yards', 'rush_yards', 'receptions', 'rec_yards'}


def inspect(data):
    rd = csv.DictReader(io.StringIO(data))
    fields = rd.fieldnames or []
    missing = REQUIRED - set(fields)
    if missing:
        raise ValueError(f'Missing required columns: {sorted(missing)}')
    if len(fields) != len(set(fields)):
        raise ValueError('Duplicate column names')
    rows = list(rd)
    if len(rows) < 1000:
        raise ValueError(f'Unexpectedly small CSV: {len(rows)} records')
    seasons = {r['season'] for r in rows}
    if len(seasons) != 1 or not next(iter(seasons)).isdigit():
        raise ValueError(f'Invalid or mixed seasons: {seasons}')
    completed = sum(r['game_status'] == 'COMPLETED' for r in rows)
    if not completed:
        raise ValueError('No completed games found')
    if any(not r['week'].isdigit() or not 1 <= int(r['week']) <= 22 for r in rows):
        raise ValueError('Invalid week values')
    return {'season': int(next(iter(seasons))), 'rows': len(rows), 'columns': len(fields),
            'completed': completed, 'fields': fields, 'sha256': hashlib.sha256(data.encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['dry-run', 'upload'], default='dry-run')
    parser.add_argument('--confirm', default='')
    args = parser.parse_args()
    if args.mode == 'upload' and args.confirm != 'UPLOAD_2026_STATS':
        raise SystemExit('Upload blocked: --confirm UPLOAD_2026_STATS required')
    new_text = CSV.read_text(encoding='utf-8-sig')
    new = inspect(new_text)
    if new['season'] != 2026:
        raise SystemExit('Only 2026 season supported by this release')
    url = os.environ['SUPABASE_URL'].rstrip('/')
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    endpoint = url + '/rest/v1/nfl_stat_exports'
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    req = Request(endpoint + '?select=season,generated_at,record_count,csv_text&season=eq.2026', headers=headers)
    with urlopen(req, timeout=120) as resp:
        existing = json.load(resp)
    if len(existing) > 1:
        raise SystemExit('Unexpected duplicate season rows')
    old = existing[0] if existing else None
    old_stats = inspect(old['csv_text']) if old and old.get('csv_text') else None
    print('New export:', json.dumps({k:v for k,v in new.items() if k != 'fields'}, indent=2))
    if old:
        print('Stored export metadata:', json.dumps({k:old.get(k) for k in ('season','generated_at','record_count')}, indent=2))
        if not old_stats:
            raise SystemExit('Existing CSV missing; cannot safely compare')
        print('Stored export:', json.dumps({k:v for k,v in old_stats.items() if k != 'fields'}, indent=2))
        if old.get('record_count') != old_stats['rows']:
            raise SystemExit('Stored record_count disagrees with stored CSV; investigate before writing')
        if new['rows'] < old_stats['rows']:
            raise SystemExit('BLOCKED: New export has fewer rows than stored export')
        if new['completed'] < old_stats['completed']:
            raise SystemExit('BLOCKED: New export has fewer completed-game records')
        missing_columns = set(old_stats['fields']) - set(new['fields'])
        if missing_columns:
            raise SystemExit('BLOCKED: New export drops columns: ' + str(sorted(missing_columns)))
        if old_stats['sha256'] == new['sha256']:
            print('Exports identical; no update needed')
            return
    if args.mode == 'dry-run':
        print('DRY RUN PASSED: database was read, not modified. No backup or upload performed.')
        return
    if old:
        backup_dir = ROOT / 'backup'
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / 'nfl_stat_exports_2026_before_upload.json'
        backup.write_text(json.dumps(old, indent=2), encoding='utf-8')
        print('Backup saved:', backup)
    else:
        raise SystemExit('BLOCKED: Existing 2026 record missing. No first-write support in this release.')
    payload = {'season': 2026, 'generated_at': datetime.now(timezone.utc).isoformat(),
               'record_count': new['rows'], 'csv_text': new_text}
    req = Request(endpoint + '?on_conflict=season', data=json.dumps(payload).encode(),
                  headers={**headers, 'Prefer':'resolution=merge-duplicates,return=minimal'}, method='POST')
    with urlopen(req, timeout=120) as resp:
        if resp.status not in (200,201,204):
            raise SystemExit('Unexpected upload status ' + str(resp.status))
    print('UPLOAD SUCCESS: season 2026 updated')


if __name__ == '__main__':
    try:
        main()
    except (HTTPError, URLError, ValueError, OSError) as exc:
        raise SystemExit(f'Phase 3A validation/upload failed: {exc}') from exc
