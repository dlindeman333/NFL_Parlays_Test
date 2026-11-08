#!/usr/bin/env python3
"""Phase 3D25: prepare a non-executable manifest and manual backup checklist. NO WRITES."""
import csv,datetime as dt,hashlib,json,pathlib,collections,sys
BASE=pathlib.Path('.');OUT=BASE/'phase3c3d25-report';OUT.mkdir(exist_ok=True)
KEY=('season','week','game_id','player_id')
def read_csv(path):
 with path.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def read_json(path):return json.loads(path.read_text(encoding='utf-8'))
def key(r):return tuple(str(r.get(k,'')).strip() for k in KEY)
def stamp(v):
 try:
  x=dt.datetime.fromisoformat(str(v).replace('Z','+00:00'))
  return x.astimezone(dt.timezone.utc) if x.tzinfo else None
 except (TypeError,ValueError,OverflowError):return None
def validate(rows,comparison,prev,now):
 if len(rows)!=41 or len(comparison)!=41:raise ValueError('Expected 41-player reference')
 if len({key(x) for x in rows})!=41 or len({key(x) for x in comparison})!=41:raise ValueError('Duplicate keys')
 if any(not all(key(x)) for x in rows):raise ValueError('Missing composite key')
 if {key(x) for x in rows}!={key(x) for x in comparison}:raise ValueError('Comparison does not match source keys')
 if not prev.get('comparison_complete') or prev.get('db_access')!='GET_ONLY' or prev.get('db_writes')!=0:raise ValueError('Live comparison incomplete or unsafe')
 if prev.get('reference_rows')!=41:raise ValueError('Comparison reference count mismatch')
 if prev.get('supabase_rows_read') is None:raise ValueError('Missing Supabase read count')
 if any(x.get('approved_for_write','').upper()!='FALSE' for x in comparison):raise ValueError('Unexpected approval')
 if any(x.get('comparison_decision') not in ('REVIEW_POTENTIAL_INSERT','REVIEW_POTENTIAL_UPDATE','HOLD_SOURCE_QUALITY','HOLD_MISSING_FIELDS','HOLD_INVALID_INCOMING_TIMESTAMP','HOLD_STORED_TIMESTAMP_UNKNOWN','BLOCK_OLDER_THAN_STORED','NO_CHANGE_EQUAL_TIMESTAMP') for x in comparison):raise ValueError('Unexpected comparison decision')
 return True
def tests():
 rows=[dict(zip(KEY,['2026','10','g'+str(i),'p'+str(i)])) for i in range(41)]
 comp=[{**r,'approved_for_write':'FALSE','comparison_decision':'HOLD_SOURCE_QUALITY'} for r in rows]
 a={'comparison_complete':True,'db_access':'GET_ONLY','db_writes':0,'reference_rows':41,'supabase_rows_read':0}
 assert validate(rows,comp,a,None)
 for variant in (lambda c:c+[c[0]],lambda c:[{**c[0],'player_id':''}]+c[1:]):
  try:validate(rows,variant(comp),a,None);raise AssertionError('Must reject')
  except ValueError:pass
 for bad in ({**a,'comparison_complete':False},{**a,'db_writes':1},{**a,'db_access':'POST'}):
  try:validate(rows,comp,bad,None);raise AssertionError('Must reject')
  except ValueError:pass
 try:validate(rows,[{**comp[0],'approved_for_write':'TRUE'}]+comp[1:],a,None);raise AssertionError('Must reject')
 except ValueError:pass
 return 7
def main():
 now=dt.datetime.now(dt.timezone.utc)
 audit={'phase':'3C-3D25','mode':'READ_ONLY_BACKUP_AND_AUTHORIZATION_PREPARATION','generated_utc':now.isoformat(),'db_writes':0,'db_deletes':0,'snapshot_writes':0,'approved_writes':0,'backup_verified':False,'rollback_tested':False,'authorized_to_execute':False,'ready_to_load':False,'status':'FAIL_CLOSED'}
 try:
  audit['safety_tests_passed']=tests()
  d22=read_json(BASE/'phase3c3d22-report/audit.json')
  d23=read_json(BASE/'phase3c3d23-report/audit.json')
  d24=read_json(BASE/'phase3c3d24-report/audit.json')
  source=read_csv(BASE/'phase3c3d23-report/storage_decision_preview_DO_NOT_IMPORT.csv')
  compare=read_csv(BASE/'phase3c3d24-report/comparison_DO_NOT_IMPORT.csv')
  validate(source,compare,d24,now)
  if d22.get('parser_validation')!='PASS' or d22.get('fully_schedule_verified')!=41:raise ValueError('Source parser or schedule verification incomplete')
  if d23.get('phase')!='3C-3D23':raise ValueError('Missing 3D23 audit')
  if d24.get('decision_counts')!=dict(collections.Counter(r['comparison_decision'] for r in compare)):raise ValueError('Audit and CSV decision counts disagree')
  sources={key(r):r for r in source}
  fields=list(KEY)+['player_name','team','designation','source_updated_at','comparison_decision','review_reason','source_age_hours_at_manifest','requires_manual_approval','would_write']
  manifest=[]
  for r in sorted(compare,key=key):
   src=sources[key(r)];ts=stamp(src.get('source_updated_at'))
   age=round((now-ts).total_seconds()/3600,2) if ts else ''
   manifest.append({**{k:r[k] for k in KEY},'player_name':src.get('player_name',''),'team':src.get('team',''),'designation':src.get('designation',''),'source_updated_at':src.get('source_updated_at',''),'comparison_decision':r['comparison_decision'],'review_reason':src.get('review_reason',''),'source_age_hours_at_manifest':age,'requires_manual_approval':'TRUE','would_write':'FALSE'})
  with (OUT/'candidate_manifest_DO_NOT_IMPORT.csv').open('w',newline='',encoding='utf-8') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(manifest)
  data=(OUT/'candidate_manifest_DO_NOT_IMPORT.csv').read_bytes()
  audit.update({'status':'PREPARATION_COMPLETE_NOT_AUTHORIZED','reference_rows':len(manifest),'live_stored_rows':d24['supabase_rows_read'],'comparison_counts':dict(collections.Counter(x['comparison_decision'] for x in manifest)),'manifest_sha256':hashlib.sha256(data).hexdigest(),'manifest_bytes':len(data),'source_generated_utc':d22.get('generated_utc'),'note':'The manifest is a point-in-time non-executable review artifact; all candidate records must be revalidated before a future write.'})
 except Exception as e:
  audit.update({'error_type':type(e).__name__,'error_message':str(e)[:180]})
 (OUT/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
 (OUT/'backup_authorization_checklist.txt').write_text("""PHASE 3D25 MANUAL PRE-WRITE CHECKLIST — NOT COMPLETED

[ ] Confirm backup coverage for public.nfl_player_injuries AND related tables.
[ ] Obtain an actual restorable database backup or provider-managed recovery point.
[ ] Record backup timestamp, storage location, responsible operator and restore procedure in a private secure location (NOT in GitHub Actions artifacts).
[ ] Independently test restore to a disposable isolated environment; verify row counts and keys.
[ ] Re-run live comparison immediately before any proposed insert; refuse if keys or timestamps changed.
[ ] Verify current official injury/inactive evidence; ESPN alone is not game-day clearance.
[ ] Review exact candidate manifest and source timestamps; do not assume all candidates should be stored.
[ ] Scope future writes strictly to public.nfl_player_injuries and the reviewed composite keys.
[ ] Capture before-images and operation IDs for any future approved writes; avoid broad deletes.
[ ] Verify rollback plan on isolated environment and test that other users/tables remain untouched.
[ ] Obtain explicit authorization for exact records, operation, environment and time.

STATUS: ALL CHECKBOXES UNVERIFIED. THIS WORKFLOW DOES NOT CREATE A BACKUP,
TEST A RESTORE, AUTHORIZE WRITES, OR PRODUCE EXECUTABLE SQL.

ROLLBACK DESIGN (NOT EXECUTED):
- For a later explicitly authorized insertion, record exact composite keys, operation ID,
  before-images, and row content hashes in a restricted audit store.
- Reverse only rows proven to have been created by that operation and still unchanged;
  otherwise stop for human review. Never truncate or delete by season/week alone.
- For updates, restore verified before-images only when current row still matches
  expected post-image; otherwise stop for human review.
- Never touch nfl_parlay_sync, prediction tables, stats, or other users' records.
""",encoding='utf-8')
 print(json.dumps(audit,indent=2))
 if audit['status']!='PREPARATION_COMPLETE_NOT_AUTHORIZED':sys.exit('Preparation failed closed; inspect audit.json')
if __name__=='__main__':main()
