#!/usr/bin/env python3
"""GET-only Supabase snapshot audit; outputs metadata only, never row contents."""
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TABLES = ('nfl_prediction_snapshots', 'nfl_prediction_grades', 'nfl_player_injuries', 'nfl_automation_runs')
OUT = Path('phase3d32-report')

def get_page(base, key, table, offset, size=500):
    url = base.rstrip('/') + '/rest/v1/' + table + '?' + urlencode({'select':'*','limit':str(size),'offset':str(offset)})
    req = Request(url, headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json','Prefer':'count=exact'},method='GET')
    with urlopen(req, timeout=30) as resp:
        raw=resp.read(8_000_000)
        if len(raw)>=8_000_000: raise ValueError('Response too large')
        data=json.loads(raw)
        if not isinstance(data,list) or len(data)>size: raise ValueError('Invalid page')
        cr=resp.headers.get('Content-Range','')
        if '/' not in cr or not cr.rsplit('/',1)[1].isdigit(): raise ValueError('Missing exact row count')
        return data,int(cr.rsplit('/',1)[1])

def audit(base,key,table):
    offset=0; total=None; fields=set(); timestamps={}; duplicates={}; timestamp_fields=[]
    while total is None or offset<total:
        rows,count=get_page(base,key,table,offset)
        if total is not None and total!=count: raise ValueError('Table changed during pagination; retry')
        total=count
        for row in rows:
            if not isinstance(row,dict): raise ValueError('Unexpected row')
            fields.update(row.keys())
            for k,v in row.items():
                if k in ('created_at','updated_at','prediction_timestamp','predicted_at','snapshot_at','generated_at') and isinstance(v,str):
                    timestamps.setdefault(k,[]).append(v)
        if not rows: break
        offset+=len(rows)
        if offset>100000: raise ValueError('Audit row cap exceeded')
    result={'row_count':total,'fields':sorted(fields),'timestamp_bounds':{k:{'earliest':min(v),'latest':max(v)} for k,v in timestamps.items() if v},'rows_examined':offset}
    if table=='nfl_prediction_snapshots':
        result['note']='Count and timestamp bounds cannot establish whether the additional snapshot was generated before kickoff; inspect source and game-time evidence before write activation.'
    return result

def main():
    OUT.mkdir(exist_ok=True)
    report={'phase':'3D32','mode':'READ_ONLY_SCHEMA_AND_SNAPSHOT_AUDIT','generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'database_writes':0,'writes_authorized':False,'tables':{},'status':'HOLD'}
    base=os.environ.get('SUPABASE_URL','').strip(); key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','').strip()
    if not base.startswith('https://') or not base.rstrip('/').endswith('.supabase.co') or not key:
        report['error']='Missing or invalid Supabase configuration'
    else:
        for table in TABLES:
            try: report['tables'][table]=audit(base,key,table)
            except Exception as exc:
                report['tables'][table]={'error_type':type(exc).__name__}
        if all('row_count' in report['tables'].get(t,{}) for t in TABLES): report['status']='PASS_READ_ONLY'
    (OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'counts':{t:v.get('row_count') for t,v in report['tables'].items()},'database_writes':0},indent=2))
    if report['status']!='PASS_READ_ONLY': raise SystemExit(1)

if __name__=='__main__': main()
