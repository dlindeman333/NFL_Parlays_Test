#!/usr/bin/env python3
"""Read-only, paginated Supabase logical backup with per-table hashes.
No POST/PATCH/DELETE. Backups contain private user data; store only as restricted CI artifact.
"""
import datetime as dt, hashlib, json, os, pathlib
from nfl_package3_live_audit import get_rows
TABLES=('nfl_parlay_sync','nfl_stat_exports','nfl_prediction_snapshots','nfl_prediction_grades','nfl_user_prediction_tracking','nfl_player_injuries','nfl_automation_runs')
PAGE=250
MAX_ROWS=200000

def fetch_all(fetch, table, page=PAGE):
    result=[]; offset=0
    while True:
        rows=fetch(table, {'select':'*','limit':str(page),'offset':str(offset)})
        if not isinstance(rows,list): raise ValueError('Invalid rows')
        result.extend(rows)
        if len(result)>MAX_ROWS: raise RuntimeError('Safety limit exceeded')
        if len(rows)<page: break
        offset+=page
    return result

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def backup(fetch, output):
    output=pathlib.Path(output);output.mkdir(parents=True,exist_ok=True)
    manifest={'mode':'READ_ONLY_LOGICAL_BACKUP','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'tables':{},'database_writes':0,'restore_verified':False}
    for table in TABLES:
        rows=fetch_all(fetch,table)
        payload=canonical(rows)
        (output/(table+'.json')).write_bytes(payload)
        manifest['tables'][table]={'rows':len(rows),'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload)}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return manifest

def main():
    for flag in ('ENABLE_GRADE_WRITES','ENABLE_PREDICTION_WRITES','ENABLE_INJURY_WRITES'):
        if os.getenv(flag,'').lower() in ('1','true','yes'): raise RuntimeError('Writes prohibited')
    url=os.environ['SUPABASE_URL']; key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    def fetch(table,query): return get_rows(url,key,table,query)
    result=backup(fetch,'package13-private-backup')
    print(json.dumps({'tables':{t:x['rows'] for t,x in result['tables'].items()},'writes':0,'restore_verified':False}))
if __name__=='__main__':main()
