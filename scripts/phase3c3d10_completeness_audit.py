#!/usr/bin/env python3
"""Read-only model identity reconciliation and ESPN injury feed coverage diagnostic."""
import csv, json, pathlib, collections, datetime, urllib.request, urllib.parse, hashlib
from phase3c3d8_injury_parser_audit import parse, norm, code, URL
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d10-report');OUT.mkdir(exist_ok=True)

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'NFL-Parlay-ReadOnly-Completeness-Audit/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=50) as response:return json.load(response)

def write_csv(path,rows,fields):
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
 report={'mode':'READ_ONLY_COMPLETENESS_AND_GAME_EVIDENCE_GAP','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'database_writes':0,'snapshot_approved':0,'game_day_inactives_verified':0,'game_specific_designations_verified':0,'limitations':['ESPN endpoint is undocumented','Larger limit returning more records does not prove complete coverage','Injury feed is not an official game-specific practice report','No official inactive list or verified game schedule used','No player is cleared for a game based on this diagnostic']}
 mapping=json.loads((ROOT/'phase3c3d8_player_ids.json').read_text())
 baseline=json.loads((ROOT/'phase3c2_model_baselines.json').read_text())
 pools=baseline.get('player_pools',{})
 unique={}
 for market,pool in pools.items():
  for entry in pool:
   if len(entry)<2:continue
   team,name=code(entry[0]),str(entry[1]);key=(team,norm(name))
   unique.setdefault(key,{'team':team,'player':name,'markets':set()})['markets'].add(market)
 mapping_by_key=collections.defaultdict(list)
 for p in mapping:mapping_by_key[(code(p['team']),norm(p['player']))].append(p)
 recon=[]
 for key,p in sorted(unique.items()):
  matches=mapping_by_key.get(key,[])
  recon.append({'baseline_team':p['team'],'baseline_player':p['player'],'markets':','.join(sorted(p['markets'])),'mapping_count':len(matches),'mapped_espn_ids':' | '.join(sorted(str(x['espn_id']) for x in matches)),'decision':'MATCHED' if len(matches)==1 else 'MISSING_MAPPING' if not matches else 'AMBIGUOUS_MAPPING'})
 extras=[p for p in mapping if (code(p['team']),norm(p['player'])) not in unique]
 report['baseline_unique_players']=len(unique);report['mapping_players']=len(mapping)
 report['reconciliation_counts']=dict(collections.Counter(x['decision'] for x in recon))
 report['mapping_only_players']=[{'team':p['team'],'player':p['player'],'espn_id':p['espn_id']} for p in extras]
 report['mapping_duplicate_ids']={k:v for k,v in collections.Counter(str(x['espn_id']) for x in mapping).items() if v>1}
 write_csv(OUT/'reconciliation.csv',recon,['baseline_team','baseline_player','markets','mapping_count','mapped_espn_ids','decision'])
 # Compare baseline/default feed to explicit larger-limit probe; neither establishes authoritative completeness.
 feed_results=[];feeds={}
 for label,url in [('default',URL),('limit_2000',URL+('?' if '?' not in URL else '&')+'limit=2000')]:
  row={'probe':label,'requested_url':url,'error':'','team_groups':None,'record_count':None,'distinct_player_ids':None,'response_timestamp':'','record_digest':''}
  try:
   data=fetch(url);rows=parse(data);feeds[label]=rows
   ids=sorted(set(str(x['espn_id']) for x in rows if x['espn_id']))
   row.update(team_groups=len(data.get('injuries',[])),record_count=len(rows),distinct_player_ids=len(ids),response_timestamp=str(data.get('timestamp','')),record_digest=hashlib.sha256('\n'.join(ids).encode()).hexdigest())
  except Exception as e:row['error']=f'{type(e).__name__}: {e}'
  feed_results.append(row)
 report['coverage_probes']=feed_results
 default_ids={str(x['espn_id']) for x in feeds.get('default',[]) if x['espn_id']}
 larger_ids={str(x['espn_id']) for x in feeds.get('limit_2000',[]) if x['espn_id']}
 report['additional_player_ids_in_limit_probe']=len(larger_ids-default_ids)
 report['coverage_conclusion']='MORE_RECORDS_OBSERVED_NOT_PROVEN_COMPLETE' if len(larger_ids-default_ids)>0 else 'COMPLETENESS_UNVERIFIED'
 best=feeds.get('limit_2000') if len(feeds.get('limit_2000',[]))>len(feeds.get('default',[])) else feeds.get('default',[])
 by_id=collections.defaultdict(list)
 for r in best:
  if r['espn_id']:by_id[str(r['espn_id'])].append(r)
 evidence=[]
 for x in recon:
  ids=x['mapped_espn_ids'].split(' | ') if x['decision']=='MATCHED' else []
  matches=[r for i in ids for r in by_id.get(i,[])]
  statuses=sorted(set(r['raw_status'] for r in matches if r['raw_status']))
  teams=sorted(set(r['team'] for r in matches if r['team']))
  conflict=any(t!=x['baseline_team'] for t in teams) or len(statuses)>1
  evidence.append({'team':x['baseline_team'],'player':x['baseline_player'],'identity_decision':x['decision'],'injury_record_count':len(matches),'reported_statuses':' | '.join(statuses),'observed_teams':' | '.join(teams),'latest_reported_date':max((r['date'] for r in matches if r['date']),default=''),'identity_or_status_conflict':conflict,'game_specific_injury_report_verified':False,'game_day_inactives_verified':False,'availability':'UNKNOWN_PENDING_GAME_SPECIFIC_EVIDENCE','snapshot_approved':False})
 write_csv(OUT/'player_evidence.csv',evidence,list(evidence[0]) if evidence else ['player'])
 report['injury_record_matches_for_baseline_players']=sum(bool(x['injury_record_count']) for x in evidence)
 report['unmatched_baseline_players']=[x['player'] for x in evidence if x['identity_decision']!='MATCHED']
 report['game_specific_evidence_gap_count']=len(evidence)
 (OUT/'audit.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2));print('READ ONLY: no Supabase access, no approvals.')
if __name__=='__main__':main()
