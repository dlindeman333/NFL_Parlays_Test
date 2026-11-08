#!/usr/bin/env python3
"""Read-only timing audit. Never accesses prediction picks or writes to Supabase."""
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = Path('phase3d33-report/timing.json')

def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return t.astimezone(dt.timezone.utc) if t.tzinfo else None
    except ValueError:
        return None

def fetch(base, key):
    rows = []
    offset = 0
    while True:
        params = urlencode({'select':'game_id,season,week,created_at,kickoff_at,model_version', 'order':'created_at.asc', 'limit':'500', 'offset':str(offset)})
        url = base.rstrip('/') + '/rest/v1/nfl_prediction_snapshots?' + params
        req = Request(url, headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'}, method='GET')
        with urlopen(req, timeout=30) as response:
            page = json.load(response)
        if not isinstance(page, list) or len(page) > 500:
            raise ValueError('Unexpected response')
        rows.extend(page)
        if len(rows) > 10000:
            raise ValueError('Safety limit exceeded')
        if len(page) < 500:
            return rows
        offset += len(page)

def evaluate(rows):
    entries = []
    for i, row in enumerate(rows, 1):
        created, kickoff = parse_time(row.get('created_at')), parse_time(row.get('kickoff_at'))
        if created is None or kickoff is None:
            status = 'UNKNOWN_TIMESTAMP'
        elif created < kickoff:
            status = 'CREATED_BEFORE_RECORDED_KICKOFF'
        else:
            status = 'CREATED_AT_OR_AFTER_RECORDED_KICKOFF'
        entries.append({'ordinal':i, 'game_id':row.get('game_id'), 'season':row.get('season'), 'week':row.get('week'), 'created_at':row.get('created_at'), 'kickoff_at':row.get('kickoff_at'), 'model_version':row.get('model_version'), 'timing_status':status})
    flagged = [e for e in entries if e['timing_status'] != 'CREATED_BEFORE_RECORDED_KICKOFF']
    return {'phase':'3D33','mode':'READ_ONLY','writes_authorized':False,'database_writes':0,'snapshot_count':len(entries),'latest_snapshot':entries[-1] if entries else None,'flagged_snapshots':flagged,'flagged_count':len(flagged),'all_snapshots':entries,'caution':'Timestamp ordering alone cannot prove a prediction was actually generated pregame, nor identify the origin of an added row.'}

def main():
    base = os.environ.get('SUPABASE_URL','')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
    if not base.startswith('https://') or not base.rstrip('/').endswith('.supabase.co') or not key:
        raise SystemExit('Supabase URL or service role key missing')
    report = evaluate(fetch(base, key))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'snapshot_count':report['snapshot_count'],'flagged_count':report['flagged_count'],'database_writes':0}))

if __name__ == '__main__':
    main()
