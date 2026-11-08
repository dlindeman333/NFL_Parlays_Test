#!/usr/bin/env python3
"""Phase 3C-3D5: read-only player identity resolution across all ESPN team rosters.
No injury clearance, game-day availability certification, or Supabase writes.
"""
import csv, json, pathlib, re, sys, urllib.request, datetime, collections, unicodedata

OUT=pathlib.Path('phase3c3d5-report'); OUT.mkdir(exist_ok=True)
TEAMS={'ARI':'ari','ATL':'atl','BAL':'bal','BUF':'buf','CAR':'car','CHI':'chi','CIN':'cin','CLE':'cle','DAL':'dal','DEN':'den','DET':'det','GB':'gb','HOU':'hou','IND':'ind','JAC':'jax','KC':'kc','LV':'lv','LAC':'lac','LA':'lar','MIA':'mia','MIN':'min','NE':'ne','NO':'no','NYG':'nyg','NYJ':'nyj','PHI':'phi','PIT':'pit','SF':'sf','SEA':'sea','TB':'tb','TEN':'ten','WAS':'wsh'}
def norm_team(s):return {'JAX':'JAC','LAR':'LA','WSH':'WAS'}.get(str(s or '').upper(),str(s or '').upper())
def norm_name(s):
 s=unicodedata.normalize('NFKD',str(s or ''));s=''.join(c for c in s if not unicodedata.combining(c)).lower()
 s=re.sub(r'\b(jr|sr|ii|iii|iv|v)\b','',s);return re.sub('[^a-z0-9]','',s)
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'NFL-Parlay-ReadOnly-Identity-Audit/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def main():
 # Generate fresh candidate roster report using the existing script, which reads but never writes to Supabase.
 sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
 import phase3c3d4_roster_injury_audit
 phase3c3d4_roster_injury_audit.main()
 prior=json.loads(pathlib.Path('phase3c3d4-report/audit.json').read_text())
 predictions=prior['predictions']; roster={}; errors={}; timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 for team,code in TEAMS.items():
  try:
   data=fetch(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{code}/roster')
   athletes=[]
   for section in data.get('athletes',[]):
    if isinstance(section,dict):athletes.extend(section.get('items',[]))
    elif isinstance(section,dict) and section.get('id'):athletes.append(section)
   if not athletes:raise ValueError('No athletes in ESPN roster response')
   for a in athletes:
    name=a.get('fullName') or a.get('displayName') or a.get('name')
    if name and a.get('id'):
     roster.setdefault(norm_name(name),[]).append({'team':team,'name':name,'espn_id':str(a['id']),'roster_status':a.get('status')})
  except Exception as exc:errors[team]=f'{type(exc).__name__}: {exc}'[:180]
 results=[]; counts=collections.Counter()
 for p in predictions:
  expected=norm_team(p['team']); name=p['player']; candidates=roster.get(norm_name(name),[])
  onteam=[c for c in candidates if c['team']==expected]
  if expected in errors:state='EXPECTED_TEAM_ROSTER_UNAVAILABLE'
  elif len(onteam)==1:state='MATCH_ON_EXPECTED_TEAM'
  elif len(onteam)>1:state='AMBIGUOUS_ON_EXPECTED_TEAM'
  elif errors:state='NOT_ON_EXPECTED_TEAM_INCOMPLETE_LEAGUE_LOOKUP'
  elif len(candidates)==1:state='MATCH_ON_DIFFERENT_TEAM_REVIEW'
  elif len(candidates)>1:state='MULTIPLE_LEAGUE_MATCHES_REVIEW'
  else:state='NO_LEAGUE_MATCH_REVIEW'
  selected=onteam[0] if len(onteam)==1 else (candidates[0] if len(candidates)==1 else {})
  result={'week':p['week'],'game':p['game'],'player':name,'expected_team':expected,'market':p['market'],
          'identity_status':state,'matched_team':selected.get('team',''),'espn_athlete_id':selected.get('espn_id',''),
          'candidate_count':len(candidates),'candidates':candidates,'injury_status':'UNKNOWN_NOT_VERIFIED',
          'inactive_status':'UNKNOWN_NOT_VERIFIED','snapshot_approved':False,
          'reason':'No verified dated injury report or game-day inactive list; identity alone is insufficient'}
  results.append(result);counts[state]+=1
 report={'mode':'READ_ONLY_IDENTITY_RESOLUTION','generated_utc':timestamp,'predictions_evaluated':len(results),
         'teams_requested':32,'teams_retrieved':32-len(errors),'roster_source_errors':errors,
         'identity_counts':dict(counts),'injury_status_verified':0,'game_day_inactive_status_verified':0,
         'approved_for_snapshot':0,'predictions':results,
         'limitations':['Roster source is current, not historical for each game date','Name matching with suffix normalization is not a unique identity proof',
         'A different-team match is diagnostic only; do not auto-correct bundled player team assignments',
         'Injury and game-day inactive statuses remain UNKNOWN until a dated independent source is integrated',
         'No Supabase writes, snapshots, or user data modifications']}
 (OUT/'audit.json').write_text(json.dumps(report,indent=2))
 with (OUT/'players.csv').open('w',newline='') as f:
  fields=['week','game','player','expected_team','market','identity_status','matched_team','espn_athlete_id','candidate_count','injury_status','inactive_status','snapshot_approved','reason']
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows({k:r.get(k) for k in fields} for r in results)
 print(json.dumps({k:v for k,v in report.items() if k not in ('predictions','limitations')},indent=2))
 print('READ ONLY. Injury status NOT verified. Zero approved snapshots.')
if __name__=='__main__':
 try:main()
 except Exception as e:print('AUDIT FAILED:',type(e).__name__,str(e),file=sys.stderr);sys.exit(1)
