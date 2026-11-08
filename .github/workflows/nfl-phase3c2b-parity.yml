#!/usr/bin/env python3
"""Read-only parity diagnostics: compare existing Python preview with browser-formula JS reference."""
import csv, io, json, os, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=Path('phase3c2b-report'); OUT.mkdir(exist_ok=True)

def main():
    url=os.environ['SUPABASE_URL'].rstrip('/')
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    query=urllib.parse.urlencode({'select':'season,generated_at,record_count,csv_text','season':'eq.2026','limit':'1'})
    req=urllib.request.Request(url+'/rest/v1/nfl_stat_exports?'+query,headers={'apikey':key,'Authorization':'Bearer '+key})
    with urllib.request.urlopen(req,timeout=60) as resp: records=json.load(resp)
    if len(records)!=1: raise RuntimeError('Expected one 2026 export')
    rec=records[0]; csv_rows=list(csv.DictReader(io.StringIO(rec['csv_text'])))
    if rec.get('record_count') is not None and int(rec['record_count'])!=len(csv_rows):raise RuntimeError('CSV row count mismatch')
    with (OUT/'source-data.json').open('w') as f: json.dump({'baselines':json.loads((ROOT/'phase3c2_model_baselines.json').read_text()),'rows':csv_rows},f)
    env=os.environ.copy()
    result=subprocess.run([sys.executable,str(ROOT/'phase3c2_preview.py')],env=env,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError('Existing Phase 3C-2 preview failed: '+result.stderr[-2000:])
    preview=json.loads(Path('phase3c2-report/preview.json').read_text())
    with (OUT/'preview.json').open('w') as f:json.dump(preview,f,indent=2)
    proc=subprocess.run(['node',str(ROOT/'phase3c2b_browser_reference.js'),str(OUT/'source-data.json'),str(OUT/'preview.json'),str(OUT/'parity.json')],capture_output=True,text=True)
    print(proc.stdout)
    if proc.stderr:print(proc.stderr,file=sys.stderr)
    report=json.loads((OUT/'parity.json').read_text()) if (OUT/'parity.json').exists() else None
    if report:
        (OUT/'source-data.json').unlink(missing_ok=True) # Do not publish raw full CSV in artifact
        print('Report:',json.dumps({k:report[k] for k in ('status','compared','passed','failed','missing_data','known_limitations')},indent=2))
    if proc.returncode:sys.exit(proc.returncode)

if __name__=='__main__':
    try:main()
    except Exception as exc:print('PARITY ERROR:',exc,file=sys.stderr);sys.exit(1)
