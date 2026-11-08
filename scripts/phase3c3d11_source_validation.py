#!/usr/bin/env python3
"""Phase 3C-3D11: read-only roster identity + injury source coverage checks.
No Supabase connection, no writes, no approvals, no claim of game-specific verification.
"""
import collections,csv,datetime,hashlib,json,pathlib,urllib.request
from phase3c3d8_injury_parser_audit import parse,norm,code,URL
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d11-report')
ROSTER='https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/jax/roster'

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'NFL-Parlay-ReadOnly-Phase3D11/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)

def athletes(data):
 groups=data.get('athletes',[]) if isinstance(data,dict) else []
 for group in groups:
  if not isinstance(group,dict):continue
  for a in (group.get('items') if isinstance(group.get('items'),list) else [group]):
   if isinstance(a,dict):yield a

def write_csv(path,rows,fields):
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def audit(fetcher=fetch):
 OUT.mkdir(exist_ok=True)
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 baseline=json.loads((ROOT/'phase3c2_model_baselines.json').read_text())
 mapping=json.loads((ROOT/'phase3c3d8_player_ids.json').read_text())
 unique={}
 for market,pool in baseline.get('player_pools',{}).items():
  for e in pool:
   if len(e)>1:
    key=(code(e[0]),norm(e[1]));unique.setdefault(key,{'team':code(e[0]),'player':str(e[1]),'markets':set()})['markets'].add(market)
 by_key=collections.defaultdict(list)
 for p in mapping:by_key[(code(p['team']),norm(p['player']))].append(p)
 recon=[];missing=[]
 for key,p in sorted(unique.items()):
  m=by_key[key];status='MAPPED' if len(m)==1 else 'MISSING_MAPPING' if not m else 'AMBIGUOUS_MAPPING'
  recon.append({'team':p['team'],'player':p['player'],'markets':','.join(sorted(p['markets'])),'status':status,'espn_id':str(m[0]['espn_id']) if len(m)==1 else ''})
  if not m:missing.append(p)
 report={'mode':'READ_ONLY_IDENTITY_AND_INJURY_COVERAGE','generated_utc':now,'baseline_count':len(unique),'mapping_count':len(mapping),'mapping_status_counts':dict(collections.Counter(x['status'] for x in recon)),'roster_identity_candidates':[],'roster_error':'','coverage_probes':[],'coverage_differences':{},'player_evidence_summary':{},'game_specific_injury_reports_verified':0,'game_day_inactives_verified':0,'snapshot_approved':0,'database_writes':0,'limitations':['ESPN endpoints are undocumented','Roster presence is not proof of game-day availability','Injury feed status is not an official game-specific practice report','No official inactive lists were consulted','No game-specific status is verified','Differences between requests do not prove pagination or completeness']}
 if missing:
  try:
   data=fetcher(ROSTER);pool=list(athletes(data))
   for p in missing:
    matches=[a for a in pool if norm(a.get('displayName') or a.get('fullName') or '')==norm(p['player'])]
    report['roster_identity_candidates'].append({'team':p['team'],'player':p['player'],'matching_roster_entries':len(matches),'candidates':[{'name':a.get('displayName') or a.get('fullName'),'espn_id':str(a.get('id') or ''),'status':a.get('status',{}).get('name','') if isinstance(a.get('status'),dict) else str(a.get('status',''))} for a in matches],'decision':'UNIQUE_ROSTER_CANDIDATE_REQUIRES_REVIEW' if len(matches)==1 and matches[0].get('id') else 'UNRESOLVED'})
  except Exception as exc:report['roster_error']=f'{type(exc).__name__}: {exc}'
 feeds={}
 for label,url in [('default',URL),('limit_2000',URL+'?limit=2000')]:
  item={'probe':label,'url':url,'error':'','timestamp':'','record_count':0,'distinct_player_ids':0,'digest':''}
  try:
   data=fetcher(url);rows=parse(data);feeds[label]=rows
   ids=sorted({str(r['espn_id']) for r in rows if r['espn_id']})
   item.update(timestamp=str(data.get('timestamp','')),record_count=len(rows),distinct_player_ids=len(ids),digest=hashlib.sha256('\n'.join(ids).encode()).hexdigest())
  except Exception as exc:item['error']=f'{type(exc).__name__}: {exc}'
  report['coverage_probes'].append(item)
 sets={k:{str(r['espn_id']) for r in v if r['espn_id']} for k,v in feeds.items()}
 a=sets.get('default',set());b=sets.get('limit_2000',set())
 report['coverage_differences']={'ids_only_default':len(a-b),'ids_only_limit_2000':len(b-a),'identical_id_sets':bool(a and b and a==b),'completeness':'UNVERIFIED'}
 by_id=collections.defaultdict(list)
 for rows in feeds.values():
  for r in rows:
   if r['espn_id']:by_id[str(r['espn_id'])].append(r)
 evidence=[]
 for r in recon:
  matches=by_id.get(r['espn_id'],[]) if r['espn_id'] else []
  statuses=sorted({x['raw_status'] for x in matches if x['raw_status']})
  observed_teams=sorted({x['team'] for x in matches if x['team']})
  evidence.append({'team':r['team'],'player':r['player'],'espn_id':r['espn_id'],'identity_status':r['status'],'injury_feed_records':len(matches),'injury_statuses':' | '.join(statuses),'injury_source_dates':' | '.join(sorted({x['date'] for x in matches if x['date']})),'team_conflict':any(x!=r['team'] for x in observed_teams),'game_specific_status':'UNVERIFIED','inactive_status':'UNVERIFIED','snapshot_approved':False})
 report['player_evidence_summary']={'mapped_with_injury_feed_record':sum(bool(x['injury_feed_records']) for x in evidence),'missing_injury_feed_record':sum(not x['injury_feed_records'] for x in evidence),'team_conflicts':sum(x['team_conflict'] for x in evidence)}
 write_csv(OUT/'identity_reconciliation.csv',recon,['team','player','markets','status','espn_id'])
 write_csv(OUT/'player_evidence.csv',evidence,['team','player','espn_id','identity_status','injury_feed_records','injury_statuses','injury_source_dates','team_conflict','game_specific_status','inactive_status','snapshot_approved'])
 (OUT/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2));print('READ ONLY: no game-day clearance, no Supabase writes.')
 return report
if __name__=='__main__':audit()
