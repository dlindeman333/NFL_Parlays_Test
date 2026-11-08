#!/usr/bin/env python3
"""Phase 3D31: actual Supabase REST read-only inventory for future workers.
Never sends POST/PATCH/DELETE and never emits records or credentials.
"""
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

TABLES = ('nfl_player_injuries','nfl_prediction_snapshots','nfl_prediction_grades','nfl_automation_runs')
OUT = Path('phase3d31-report')

def endpoint(base, table):
    if not base.startswith('https://') or not base.rstrip('/').endswith('.supabase.co'):
        raise ValueError('Expected an HTTPS Supabase project URL')
    if table not in TABLES:
        raise ValueError('Unapproved table')
    return base.rstrip('/') + '/rest/v1/' + table + '?' + urlencode({'select':'*','limit':'1'})

def fetch_count(base, key, table):
    request=Request(endpoint(base,table),headers={
        'apikey':key,'Authorization':'Bearer '+key,
        'Prefer':'count=exact','Range':'0-0','Accept':'application/json'},method='GET')
    with urlopen(request,timeout=25) as response:
        body=response.read(100000)
        if len(body)>=100000: raise ValueError('Unexpectedly large response')
        rows=json.loads(body)
        if not isinstance(rows,list) or len(rows)>1: raise ValueError('Unexpected response shape')
        content_range=response.headers.get('Content-Range','')
        if '/' not in content_range or not content_range.rsplit('/',1)[1].isdigit():
            raise ValueError('Missing exact count')
        # Do not log rows: they may contain user or prediction data.
        return {'row_count':int(content_range.rsplit('/',1)[1]),'reachable':True}

def main():
    OUT.mkdir(exist_ok=True)
    report={'phase':'3D31','mode':'LIVE_READ_ONLY_WORKER_INVENTORY',
        'generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'database_writes':0,'writes_authorized':False,'snapshot_created':False,
        'grading_performed':False,'tables':{},'status':'HOLD',
        'limitations':['Counts only; no production snapshot or grading worker implemented.',
          'No restore verification; write activation prohibited.',
          'No historical prediction backfilling.']}
    base=os.environ.get('SUPABASE_URL','').strip()
    key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','').strip()
    if not base or not key:
        report['error']='Required secrets missing'
    else:
        for table in TABLES:
            try: report['tables'][table]=fetch_count(base,key,table)
            except (ValueError,HTTPError,URLError,TimeoutError) as exc:
                report['tables'][table]={'reachable':False,'error_type':type(exc).__name__}
        if all(report['tables'].get(t,{}).get('reachable') for t in TABLES):
            report['status']='PASS_READ_ONLY'
    (OUT/'inventory.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'tables':report['tables'],'database_writes':0},indent=2))
    if report['status']!='PASS_READ_ONLY': raise SystemExit(1)

if __name__=='__main__':main()
