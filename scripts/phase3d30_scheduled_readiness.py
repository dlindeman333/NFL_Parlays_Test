#!/usr/bin/env python3
"""Summarize existing read-only phase 3 diagnostics. Never connects to or writes to Supabase."""
import json, pathlib, datetime, sys
ROOT=pathlib.Path('.')
SOURCES={
 'initial_load':'phase3c3d22-report/audit.json',
 'storage_decisions':'phase3c3d23-report/audit.json',
 'live_comparison':'phase3c3d24-report/audit.json',
 'candidate_manifest':'phase3c3d25-report/audit.json',
 'automation_gates':'phase3d27-29-report/automation_readiness.json',
}
result={'phase':'3D30','mode':'SCHEDULED_READ_ONLY','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'sources':{},'checks':{},'writes_authorized':False,'database_writes':0}
for label, path in SOURCES.items():
    p=ROOT/path
    if not p.is_file():
        result['sources'][label]={'present':False}
        continue
    try:
        obj=json.loads(p.read_text(encoding='utf-8'))
        result['sources'][label]={'present':True,'mode':obj.get('mode'), 'phase':obj.get('phase')}
        if label=='automation_gates':
            result['checks']['all_safety_tests_pass']=obj.get('checks_passed')==obj.get('checks_total') and obj.get('checks_total',0)>0 and all(obj.get('checks',{}).values())
        if label=='live_comparison':
            result['checks']['live_comparison_read_only']=obj.get('db_writes')==0 and obj.get('db_deletes')==0 and obj.get('db_access')=='GET_ONLY'
        if label=='initial_load':
            result['checks']['schedule_verified']=obj.get('schedule_validation')=='COMPLETE' and obj.get('parser_validation')=='PASS'
    except (OSError,ValueError) as e:
        result['sources'][label]={'present':False,'error_type':type(e).__name__}
result['checks']['all_reports_present']=all(v['present'] for v in result['sources'].values())
result['status']='PASS' if result['checks'] and all(result['checks'].values()) else 'HOLD'
out=ROOT/'phase3d30-report';out.mkdir(exist_ok=True)
(out/'readiness.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':result['status'],'checks':result['checks'],'writes':0},indent=2))
sys.exit(0 if result['status']=='PASS' else 1)
