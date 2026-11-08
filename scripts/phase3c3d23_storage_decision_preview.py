#!/usr/bin/env python3
"""Phase 3D23: evaluate Phase 3D22 preview and test safe sync decisions. NO DB access."""
import csv, json, pathlib, datetime as dt, collections, sys
IN=pathlib.Path('phase3c3d22-report'); OUT=pathlib.Path('phase3c3d23-report')
OUT.mkdir(exist_ok=True)
SCHEMA=('season','week','game_id','player_id','player_name','team','designation','practice_status','source','source_updated_at','fetched_at')
def parse(s):
 try:
  d=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'))
  return d.astimezone(dt.timezone.utc) if d.tzinfo else None
 except (ValueError, TypeError):return None
def decision(row,existing=None):
 """A proposed storage action is never authorized by this function."""
 if row.get('schedule_check')!='VERIFIED':return 'BLOCK_SCHEDULE_UNVERIFIED'
 if not all(str(row.get(k,'')).strip() for k in ('season','week','game_id','player_id','team')):return 'BLOCK_REQUIRED_IDENTITY'
 if row.get('injury_check')!='RECENT_UNOFFICIAL':return 'HOLD_'+str(row.get('injury_check') or 'UNKNOWN')
 if not row.get('designation'):return 'HOLD_MISSING_DESIGNATION'
 t=parse(row.get('source_updated_at'))
 if not t:return 'HOLD_INVALID_SOURCE_TIME'
 if existing is None:return 'REVIEW_NEW_UNOFFICIAL_RECORD'
 old=parse(existing.get('source_updated_at'))
 if old is None:return 'HOLD_EXISTING_TIMESTAMP_UNKNOWN'
 if t<old:return 'BLOCK_OLDER_THAN_STORED'
 if t==old:return 'NO_CHANGE_EQUAL_TIMESTAMP'
 return 'REVIEW_NEWER_UNOFFICIAL_RECORD'
def tests():
 r={'season':'2026','week':'10','game_id':'401873065','player_id':'3043078','team':'BAL','designation':'Questionable','schedule_check':'VERIFIED','injury_check':'RECENT_UNOFFICIAL','source_updated_at':'2026-11-07T12:00:00+00:00'}
 cases=[('new',r,None,'REVIEW_NEW_UNOFFICIAL_RECORD'),('older',r,{'source_updated_at':'2026-11-08T12:00:00Z'},'BLOCK_OLDER_THAN_STORED'),('same',r,{'source_updated_at':'2026-11-07T12:00:00Z'},'NO_CHANGE_EQUAL_TIMESTAMP'),('newer',r,{'source_updated_at':'2026-11-06T12:00:00Z'},'REVIEW_NEWER_UNOFFICIAL_RECORD')]
 for name,base,old,expected in cases:assert decision(base,old)==expected,name
 for field,value,expected in [('schedule_check','KICKOFF_MISMATCH','BLOCK_SCHEDULE_UNVERIFIED'),('player_id','','BLOCK_REQUIRED_IDENTITY'),('injury_check','NO_INJURY_RECORD','HOLD_NO_INJURY_RECORD'),('injury_check','STALE_OR_FUTURE','HOLD_STALE_OR_FUTURE'),('designation','','HOLD_MISSING_DESIGNATION'),('source_updated_at','','HOLD_INVALID_SOURCE_TIME')]:
  x=dict(r);x[field]=value;assert decision(x)==expected,field
 assert decision(r,{'source_updated_at':'bad'})=='HOLD_EXISTING_TIMESTAMP_UNKNOWN'
 return len(cases)+7
def main():
 passed=tests(); src=json.loads((IN/'audit.json').read_text())
 with (IN/'initial_load_preview_DO_NOT_IMPORT.csv').open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
 audit={'phase':'3C-3D23','mode':'READ_ONLY_STORAGE_DECISION_PREVIEW','source_phase':src.get('phase'), 'source_parser_validation':src.get('parser_validation'),'source_schedule_validation':src.get('schedule_validation'),'reference_players':len(rows),'unit_tests_passed':passed,'db_access':'NONE','db_writes':0,'db_deletes':0,'snapshot_approvals':0,'import_ready':False,'limitations':['ESPN is unofficial; no official inactive verification','No Supabase connection; stored timestamps and existing records cannot be compared live','Decisions are illustrative only, not authorization for database inserts','Only 41 model reference players; not a complete league-wide feed','Missing/stale/unknown injury records must never delete stored records']}
 keys=[tuple(row[k] for k in ('season','week','game_id','player_id')) for row in rows]
 audit['duplicate_composite_keys']=len(keys)-len(set(keys))
 audit['source_schedule_verified']=src.get('fully_schedule_verified')
 audit['source_injury_counts']=src.get('injury_check_counts')
 results=[]
 for r in rows:
  status=decision(r)
  results.append({**{k:r.get(k,'') for k in SCHEMA},'storage_review_decision':status,'would_insert':'FALSE','would_update':'FALSE','would_delete':'FALSE','game_day_eligible':'FALSE','review_notes':'No live database comparison or official inactive clearance'})
 audit['decision_counts']=dict(collections.Counter(r['storage_review_decision'] for r in results))
 audit['requires_manual_approval']=True
 audit['approved_for_write']=0
 with (OUT/'storage_decision_preview_DO_NOT_IMPORT.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 (OUT/'audit.json').write_text(json.dumps(audit,indent=2))
 (OUT/'sync_safeguard_tests.json').write_text(json.dumps({'passed':passed,'scenarios':['new unofficial candidate requires review','older data cannot overwrite newer stored data','equal timestamp is no-change','newer data requires review','kickoff mismatch blocks','missing identity blocks','missing injury holds','stale injury holds','missing designation holds','invalid source timestamp holds','unknown stored timestamp holds']},indent=2))
 print(json.dumps(audit,indent=2))
 if src.get('parser_validation')!='PASS' or src.get('schedule_validation')!='COMPLETE' or len(rows)!=41 or audit['duplicate_composite_keys']:
  raise SystemExit('Prerequisite failed: inspect audit artifact. No data changed.')
if __name__=='__main__':main()
