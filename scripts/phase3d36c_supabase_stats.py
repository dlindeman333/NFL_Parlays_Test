#!/usr/bin/env python3
"""Read-only preview from nfl_stat_exports.csv_text; no Supabase mutation methods."""
import csv
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request

from phase3d36b_stats_candidates import REQUIRED, preview

MAX_CSV_BYTES = 12_000_000

def validate_project_url(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and bool(re.fullmatch(r'[a-z0-9-]+\.supabase\.co', p.hostname or '')) and not (p.path or p.query or p.fragment or p.username)

def fetch_latest(url, key, season):
    if not validate_project_url(url):
        raise ValueError('Invalid Supabase project URL')
    params = urllib.parse.urlencode({'select':'season,generated_at,record_count,csv_text','season':f'eq.{season}', 'order':'generated_at.desc','limit':'1'})
    req = urllib.request.Request(url.rstrip('/') + '/rest/v1/nfl_stat_exports?' + params,
        headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'}, method='GET')
    with urllib.request.urlopen(req, timeout=40) as response:
        data = response.read(MAX_CSV_BYTES + 100_000)
    if len(data) > MAX_CSV_BYTES + 100_000:
        raise ValueError('Supabase response too large')
    rows = json.loads(data)
    if not isinstance(rows,list) or len(rows)>1:
        raise ValueError('Unexpected export response')
    return rows[0] if rows else None

def analyze_export(export, season=2026):
    if export is None:
        return {'status':'no_export_for_season','eligible_unique_players':0}
    csv_text = export.get('csv_text')
    if not isinstance(csv_text,str) or not csv_text.strip():
        return {'status':'empty_csv_text','eligible_unique_players':0}
    if len(csv_text.encode('utf-8')) > MAX_CSV_BYTES:
        return {'status':'csv_too_large','eligible_unique_players':0}
    reader = csv.DictReader(io.StringIO(csv_text, newline=''))
    cols = reader.fieldnames or []
    missing = sorted(set(REQUIRED) - set(cols))
    summary = {'status':'missing_columns' if missing else 'ok','season':season,
               'generated_at':export.get('generated_at'), 'declared_record_count':export.get('record_count'),
               'csv_sha256':hashlib.sha256(csv_text.encode('utf-8')).hexdigest(),
               'csv_columns':cols,'missing_required_columns':missing}
    if missing:
        summary['eligible_unique_players']=0
        return summary
    # No source rows are written to disk. Only a capped, derived projection sample is returned.
    result = preview(reader,season)
    summary.update(result)
    summary['candidates'] = result['candidates'][:15]
    summary['sample_limit'] = 15
    return summary

def main():
    report={'phase':'3D36C','mode':'READ_ONLY','database_writes':0,
            'authentic_prediction_snapshots_created':0,'grades_created':0,
            'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'limitations':['Projection baseline only; not calibrated AI picks or sportsbook odds',
                           'The CSV source must be checked for completed-game-only and point-in-time integrity',
                           'No opponent defense adjustment; no historical snapshot backfill',
                           'No writes or secret/raw CSV contents in the artifact']}
    try:
        url=os.environ['SUPABASE_URL'].rstrip('/')
        key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
        season=int(os.getenv('NFL_SEASON','2026'))
        if season < 2000 or season > 2100: raise ValueError('Invalid season')
        report['stats']=analyze_export(fetch_latest(url,key,season),season)
    except Exception as exc:
        report['stats']={'status':'error','error_type':type(exc).__name__}
    Path('phase3d36c_stats_preview.json').write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['stats']['status'],
                      'eligible_players':report['stats'].get('eligible_unique_players',0),'writes':0}))
    if report['stats']['status'] not in ('ok','missing_columns','no_export_for_season','empty_csv_text'):
        raise SystemExit(1)

if __name__=='__main__': main()
