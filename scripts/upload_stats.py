"""Upload an already-generated CSV to the existing nfl_stat_exports season row.
Requires SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY; run only in trusted CI.
"""
import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

path = Path(__file__).resolve().parents[1] / 'nfl_player_stats.csv'
url = os.environ['SUPABASE_URL'].rstrip('/')
key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
text = path.read_text(encoding='utf-8-sig')
reader = csv.DictReader(io.StringIO(text))
required = {'season', 'week', 'game_status', 'player_id', 'team', 'pass_yards', 'rush_yards', 'receptions', 'rec_yards'}
if not reader.fieldnames or not required.issubset(reader.fieldnames):
    raise SystemExit('CSV missing grading fields: ' + str(sorted(required - set(reader.fieldnames or []))))
rows = list(reader)
if len(rows) < 1000:
    raise SystemExit(f'Refusing upload: only {len(rows)} rows; previous export had 7,798')
seasons = {r['season'] for r in rows}
if len(seasons) != 1 or not next(iter(seasons)).isdigit():
    raise SystemExit('Refusing upload: invalid or mixed seasons')
season = int(next(iter(seasons)))
if not any(r.get('game_status') == 'COMPLETED' for r in rows):
    raise SystemExit('Refusing upload: no completed player-game rows')
# Don't silently replace an existing richer export with one that has dramatically fewer rows.
endpoint = f'{url}/rest/v1/nfl_stat_exports'
headers = {'apikey': key, 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
req = Request(f'{endpoint}?select=record_count&season=eq.{season}', headers=headers)
with urlopen(req, timeout=40) as response:
    existing = json.load(response)
if existing and len(rows) < existing[0]['record_count'] * 0.70:
    raise SystemExit('Refusing upload: row count fell more than 30% compared with stored export')
payload = {'season': season, 'generated_at': datetime.now(timezone.utc).isoformat(), 'record_count': len(rows), 'csv_text': text}
req = Request(endpoint + '?on_conflict=season', data=json.dumps(payload).encode('utf-8'), headers={**headers, 'Prefer': 'resolution=merge-duplicates,return=minimal'}, method='POST')
try:
    with urlopen(req, timeout=120) as response:
        if response.status not in (200, 201, 204):
            raise SystemExit('Unexpected upload status: ' + str(response.status))
except HTTPError as exc:
    raise SystemExit(f'Supabase upload failed HTTP {exc.code}: {exc.read(1000).decode("utf-8", "replace")}') from exc
except URLError as exc:
    raise SystemExit(f'Supabase connection failed: {exc.reason}') from exc
print(f'Uploaded {len(rows)} rows for season {season} successfully')
