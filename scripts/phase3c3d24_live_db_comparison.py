#!/usr/bin/env python3
"""3D24: read-only Supabase comparison; no mutations or approvals."""
import csv, json, os, re, collections, datetime as dt, urllib.parse, urllib.request
from pathlib import Path
OUT=Path('phase3c3d24-report');OUT.mkdir(exist_ok=True)
KEY=('season','week','game_id','player_id')
COLUMNS=KEY+('player_name','team','designation','practice_status','source','source_updated_at','fetched_at')
def stamp(x):
 try:
  v=dt.datetime.fromisoformat(str(x).replace('Z','+00:00'))
  return v.astimezone(dt.timezone.utc) if v.tzinfo else None
 except (ValueError,TypeError):return None
def key(r):return tuple(str(r.get(k) if r.get(k) is not None else '').strip() for k in KEY)
def compare(row,old):
 if row.get('storage_review_decision')!='REVIEW_NEW_UNOFFICIAL_RECORD':return 'HOLD_SOURCE_QUALITY'
 if not all(key(row)) or not row.get('designation'):return 'HOLD_MISSING_FIELDS'
 new=stamp(row.get('source_updated_at'))
 if not new:return 'HOLD_INVALID_INCOMING_TIMESTAMP'
 if old is None:return 'REVIEW_POTENTIAL_INSERT'
 previous=stamp(old.get('source_updated_at'))
 if not previous:return 'HOLD_STORED_TIMESTAMP_UNKNOWN'
 if new<previous:return 'BLOCK_OLDER_THAN_STORED'
 if new==previous:return 'NO_CHANGE_EQUAL_TIMESTAMP'
 return 'REVIEW_POTENTIAL_UPDATE'
def tests():
 r=dict(zip(KEY,['2026','10','123','456']));r.update(designation='Out',source_updated_at='2026-11-08T12:00:00Z',storage_review_decision='REVIEW_NEW_UNOFFICIAL_RECORD')
 cases=[(None,'REVIEW_POTENTIAL_INSERT'),({'source_updated_at':'2026-11-09T12:00:00Z'},'BLOCK_OLDER_THAN_STORED'),({'source_updated_at':'2026-11-08T12:00:00Z'},'NO_CHANGE_EQUAL_TIMESTAMP'),({'source_updated_at':'2026-11-07T12:00:00Z'},'REVIEW_POTENTIAL_UPDATE'),({'source_updated_at':None},'HOLD_STORED_TIMESTAMP_UNKNOWN')]
 for old,expect in cases:assert compare(r,old)==expect
 assert compare({**r,'storage_review_decision':'HOLD_STALE_OR_FUTURE'},None)=='HOLD_SOURCE_QUALITY'
 assert compare({**r,'player_id':''},None)=='HOLD_MISSING_FIELDS'
 assert compare({**r,'source_updated_at':''},None)=='HOLD_INVALID_INCOMING_TIMESTAMP'
 return 8
def fetch():
 url=os.environ.get('SUPABASE_URL','').rstrip('/');secret=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
 parsed=urllib.parse.urlsplit(url)
 if not secret or parsed.scheme!='https' or not parsed.hostname or not re.fullmatch(r'[a-z0-9-]+\.supabase\.co',parsed.hostname) or parsed.path or parsed.query or parsed.fragment:raise RuntimeError('Supabase secrets missing or URL invalid')
 rows=[]
 for offset in range(0,10000,1000):
  q=urllib.parse.urlencode({'select':','.join(COLUMNS),'limit':1000,'offset':offset})
  req=urllib.request.Request(url+'/rest/v1/nfl_player_injuries?'+q,headers={'apikey':secret,'Authorization':'Bearer '+secret,'Accept':'application/json'},method='GET')
  with urllib.request.urlopen(req,timeout=35) as response:batch=json.load(response)
  if not isinstance(batch,list):raise RuntimeError('Unexpected Supabase response')
  rows+=batch
  if len(batch)<1000:return rows
 raise RuntimeError('Supabase row safety cap reached')
def main():
 audit={'phase':'3C-3D24','mode':'READ_ONLY_LIVE_COMPARISON','db_access':'GET_ONLY','db_writes':0,'db_deletes':0,'snapshot_writes':0,'approved_for_write':0,'import_ready':False,'comparison_complete':False}
 try:
  audit['unit_tests_passed']=tests()
  with Path('phase3c3d23-report/storage_decision_preview_DO_NOT_IMPORT.csv').open(newline='') as f:incoming=list(csv.DictReader(f))
  keys=[key(r) for r in incoming]
  if len(incoming)!=41 or len(keys)!=len(set(keys)) or any(not all(k) for k in keys):raise RuntimeError('Incoming reference keys invalid')
  stored=fetch();audit['supabase_rows_read']=len(stored)
  bykey=collections.defaultdict(list)
  for r in stored:bykey[key(r)].append(r)
  if any(len(v)>1 for v in bykey.values()):raise RuntimeError('Duplicate stored composite keys')
  results=[]
  for r in incoming:
   old=bykey.get(key(r),[]);o=old[0] if old else None
   results.append({'season':r['season'],'week':r['week'],'game_id':r['game_id'],'player_id':r['player_id'],'player_name':r['player_name'],'incoming_review':r['storage_review_decision'],'stored_row_exists':bool(old),'stored_source_updated_at':o.get('source_updated_at') if o else '', 'comparison_decision':compare(r,o),'approved_for_write':'FALSE'})
  audit['reference_rows']=len(results);audit['stored_rows_outside_reference']=sum(key(r) not in set(keys) for r in stored)
  audit['decision_counts']=dict(collections.Counter(r['comparison_decision'] for r in results));audit['comparison_complete']=True
  with (OUT/'comparison_DO_NOT_IMPORT.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
  (OUT/'approval_and_rollback_plan.txt').write_text('No writes or backup were performed. Before any future approved write: verify a restorable backup, require explicit confirmation, record before-images, use an audited transaction and exact composite keys; never delete missing feed rows. Preserve all other tables and users.\n')
 except Exception as e:audit['error_type']=type(e).__name__;audit['error_message']=str(e)[:160] if not hasattr(e,'code') else 'HTTP '+str(e.code)
 audit['limitations']=['Only 41 reference players','ESPN unofficial; no official game-day clearance','Review candidates are not approved writes','No backup or rollback performed']
 (OUT/'audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))
 if not audit['comparison_complete']:raise SystemExit('Comparison incomplete; see audit artifact')
if __name__=='__main__':main()
