#!/usr/bin/env python3
"""Read-only diagnostic; injury feed != game-specific availability."""
import collections,csv,datetime,json,pathlib,urllib.request
from phase3c3d8_injury_parser_audit import parse,code,URL
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d9-report');OUT.mkdir(exist_ok=True)
UTC=datetime.timezone.utc
NOW=datetime.datetime.now(UTC)
def dt(v):
 try:return datetime.datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(UTC)
 except (ValueError,TypeError,AttributeError):return None
def main():
 mapping=json.loads((ROOT/'phase3c3d8_player_ids.json').read_text())
 report={'mode':'READ_ONLY_INJURY_FRESHNESS_DIAGNOSTIC','generated_utc':NOW.isoformat(),'source':URL,'source_error':None,'model_players':len(mapping),'expected_previous_baseline_players':41,'baseline_reconciliation':'UNRESOLVED: 41-player source baseline not supplied to this workflow','game_specific_designations_verified':0,'game_day_inactives_verified':0,'snapshot_approved':0,'database_writes':0,'limitations':['ESPN endpoint undocumented; feed completeness not verified','Status date may describe last injury update, not official game report publication','No verified game schedule or game-specific report; freshness is diagnostic only','Active is not game-day clearance','No record is UNKNOWN, not healthy','No game-day inactive source','40-player mapping vs 41-player baseline remains unresolved']}
 results=[];raw=[]
 try:
  req=urllib.request.Request(URL,headers={'User-Agent':'NFL-Parlay-ReadOnly-Diagnostic/1.0','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=50) as response:data=json.load(response)
  raw=parse(data)
  report.update({'source_timestamp':data.get('timestamp'),'team_groups':len(data.get('injuries',[])),'injury_records':len(raw),'parsed_player_ids':sum(bool(r['espn_id']) for r in raw),'parsed_teams':sum(bool(r['team']) for r in raw)})
  source_dt=dt(data.get('timestamp'))
  report['feed_timestamp_age_hours']=round((NOW-source_dt).total_seconds()/3600,2) if source_dt else None
  for p in mapping:
   matches=[r for r in raw if str(r['espn_id'])==str(p['espn_id'])]
   expected=code(p['team']); conflict=any(r['team']!=expected for r in matches)
   unique={(r['espn_id'],r['team']) for r in matches}
   statuses=sorted({r['raw_status'].strip().upper() for r in matches if r['raw_status'].strip()})
   dates=[dt(r['date']) for r in matches];dates=[d for d in dates if d]
   latest=max(dates) if dates else None
   age=round((NOW-latest).total_seconds()/3600,2) if latest else None
   if not matches:decision='UNKNOWN_NO_RECORD'
   elif conflict or len(unique)>1 or len(statuses)>1:decision='REVIEW_CONFLICT'
   elif not statuses:decision='UNKNOWN_NO_STATUS'
   elif statuses[0] in ('OUT','INJURED RESERVE','IR'):decision='BLOCK_REPORTED_OUT_OR_IR'
   elif statuses[0] in ('QUESTIONABLE','DOUBTFUL'):decision='HOLD_UNCERTAIN'
   elif statuses[0]=='ACTIVE':decision='UNVERIFIED_ESPN_ACTIVE'
   else:decision='REVIEW_UNRECOGNIZED_STATUS'
   # A stale or missing record must never be treated as cleared.
   freshness='NO_RECORD' if not matches else 'MISSING_TIMESTAMP' if latest is None else 'FUTURE_TIMESTAMP_REVIEW' if age < -1 else 'OLDER_THAN_48H' if age>48 else 'WITHIN_48H_DIAGNOSTIC_ONLY'
   results.append({'player':p['player'],'team':expected,'espn_id':p['espn_id'],'record_count':len(matches),'statuses':' | '.join(statuses),'latest_record_date_utc':latest.isoformat() if latest else '', 'record_age_hours':age if age is not None else '', 'freshness':freshness,'decision':decision,'game_specific_report_verified':False,'game_day_inactive_verified':False,'snapshot_approved':False})
  report['decision_counts']=dict(collections.Counter(x['decision'] for x in results))
  report['freshness_counts']=dict(collections.Counter(x['freshness'] for x in results))
  report['coverage_warning']='800-record cap/completeness not established' if len(raw)>=800 else 'Feed completeness still unverified'
 except Exception as e:report['source_error']=f'{type(e).__name__}: {e}'
 if results:
  with (OUT/'players.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 (OUT/'audit.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2));print('READ ONLY. No approvals, no database writes.')
if __name__=='__main__':main()
