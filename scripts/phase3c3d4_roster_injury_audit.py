#!/usr/bin/env python3
"""Phase 3C-3D4: read-only roster/injury evidence audit; never certifies active status."""
import csv, io, json, os, sys, urllib.parse, urllib.request, pathlib, datetime, collections, re
ROOT=pathlib.Path('phase3c3d4-report'); ROOT.mkdir(exist_ok=True)
ALIASES={'JAX':'JAC','LAR':'LA','WSH':'WAS','LA':'LAR','WAS':'WSH'}
ESPN_TEAMS={'ARI':'ari','ATL':'atl','BAL':'bal','BUF':'buf','CAR':'car','CHI':'chi','CIN':'cin','CLE':'cle','DAL':'dal','DEN':'den','DET':'det','GB':'gb','HOU':'hou','IND':'ind','JAC':'jax','KC':'kc','LV':'lv','LAC':'lac','LA':'lar','MIA':'mia','MIN':'min','NE':'ne','NO':'no','NYG':'nyg','NYJ':'nyj','PHI':'phi','PIT':'pit','SF':'sf','SEA':'sea','TB':'tb','TEN':'ten','WAS':'wsh'}
def norm_team(t):
 t=str(t or '').strip().upper(); return {'JAX':'JAC','LAR':'LA','WSH':'WAS'}.get(t,t)
def norm_name(s): return re.sub(r'[^a-z0-9]','',str(s or '').lower())
def fetch(url,headers=None):
 req=urllib.request.Request(url,headers=headers or {'User-Agent':'NFL-Parlay-Phase3C-ReadOnly/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=35) as resp:return json.load(resp)
def main():
 base=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
 key=os.environ['SUPABASE_SERVICE_ROLE_KEY']; headers={'apikey':key,'Authorization':'Bearer '+key}
 q=urllib.parse.urlencode({'select':'season,generated_at,record_count,csv_text','season':'eq.2026','limit':'1'})
 data=fetch(base+'nfl_stat_exports?'+q,headers)
 if len(data)!=1:raise ValueError('Expected one 2026 stats export')
 ex=data[0]; rows=list(csv.DictReader(io.StringIO(ex['csv_text'])))
 if ex.get('record_count') is not None and len(rows)!=int(ex['record_count']):raise ValueError('Stats record count mismatch')
 # Use the existing read-only prediction preview; it will create its own local artifact.
 sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
 import phase3c2_preview
 phase3c2_preview.preview()
 preview=json.loads(pathlib.Path('phase3c2-report/preview.json').read_text())
 predictions=preview.get('predictions',[])
 teams=sorted({norm_team(p['team']) for p in predictions})
 rosters={};errors={}; retrieved={}
 for team in teams:
  code=ESPN_TEAMS.get(team)
  if not code:errors[team]='Unsupported team code';continue
  url=f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{code}/roster'
  try:
   response=fetch(url); athletes=[]
   for section in response.get('athletes',[]):
    if isinstance(section,dict):athletes.extend(section.get('items',[]))
   # Some response versions expose athletes as a flat list.
   if not athletes:
    athletes=[a for a in response.get('athletes',[]) if isinstance(a,dict) and a.get('id')]
   if not athletes:raise ValueError('No roster athlete entries; unsupported or empty response')
   rosters[team]=collections.defaultdict(list)
   for a in athletes:
    name=a.get('fullName') or a.get('displayName') or a.get('name')
    if name:rosters[team][norm_name(name)].append({'name':name,'espn_athlete_id':str(a.get('id','')),'status':a.get('status')})
   retrieved[team]={'athletes':len(athletes),'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_url':url}
  except Exception as e:errors[team]=f'{type(e).__name__}: {e}'[:240]
 results=[]; counts=collections.Counter()
 for p in predictions:
  team=norm_team(p.get('team')); name=p.get('player',''); matches=rosters.get(team,{}).get(norm_name(name),[])
  if team in errors: roster_status='ROSTER_SOURCE_UNAVAILABLE'
  elif len(matches)==1:roster_status='EXACT_NAME_ON_TEAM_ROSTER'
  elif len(matches)>1:roster_status='AMBIGUOUS_ROSTER_NAME'
  else:roster_status='NOT_FOUND_ON_TEAM_ROSTER'
  # A roster listing alone is NOT a game-day availability or injury clearance.
  injury_status='UNVERIFIED_NO_INJURY_REPORT'; game_day_status='UNVERIFIED_NO_INACTIVES_LIST'
  results.append({'week':p.get('week'),'game':p.get('game'),'team':team,'player':name,'market':p.get('market'),'historical_games':p.get('historical_games'),'roster_status':roster_status,'espn_athlete_id':matches[0]['espn_athlete_id'] if len(matches)==1 else '', 'roster_reported_status':str(matches[0].get('status') or '') if len(matches)==1 else '', 'injury_status':injury_status,'game_day_status':game_day_status,'snapshot_approved':False,'reason':'Roster evidence is not verified injury/inactive clearance'})
  counts[roster_status]+=1
 now=datetime.datetime.now(datetime.timezone.utc)
 report={'mode':'READ_ONLY_ROSTER_INJURY_EVIDENCE_AUDIT','generated_utc':now.isoformat(),'status':'REVIEW_REQUIRED_NO_WRITES','stats_export_generated_at':ex.get('generated_at'),'stats_rows':len(rows),'predictions_evaluated':len(results),'teams_requested':len(teams),'teams_roster_retrieved':len(retrieved),'roster_result_counts':dict(counts),'injury_status_verified':0,'game_day_inactive_status_verified':0,'approved_for_snapshot':0,'roster_sources':retrieved,'roster_source_errors':errors,'predictions':results,'limitations':['ESPN roster is a current roster lookup, not a dated roster for a past/future game','Exact normalized name matches do not prove identity when names are duplicated or a player changed teams','No verified injury report or game-day inactive feed is connected; all predictions remain blocked','ESPN roster status text is diagnostic only, never proof of active game-day eligibility','Existing snapshots and user data are not modified; no database writes']}
 (ROOT/'audit.json').write_text(json.dumps(report,indent=2))
 with (ROOT/'players.csv').open('w',newline='') as f:
  fields=['week','game','team','player','market','historical_games','roster_status','espn_athlete_id','roster_reported_status','injury_status','game_day_status','snapshot_approved','reason'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(results)
 print(json.dumps({k:v for k,v in report.items() if k not in ('predictions','roster_sources','limitations')},indent=2))
 print('READ ONLY: no Supabase INSERT, UPDATE, UPSERT, DELETE. No player certified active.')
if __name__=='__main__':
 try:main()
 except Exception as exc:print('AUDIT FAILED:',type(exc).__name__,str(exc),file=sys.stderr);sys.exit(1)
