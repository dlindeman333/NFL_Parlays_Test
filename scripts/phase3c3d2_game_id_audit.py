#!/usr/bin/env python3
"""Phase 3C-3D2: strictly read-only ESPN game-ID cross-check. No writes."""
import csv,io,json,os,sys,urllib.request,urllib.parse,collections,datetime,pathlib
OUT=pathlib.Path('phase3c3d2-report');OUT.mkdir(exist_ok=True)
ALIASES={'JAX':'JAC','LAR':'LA','WSH':'WAS','JAC':'JAC','LA':'LA','WAS':'WAS'}
def norm(s):
 s=str(s or '').strip().upper();return ALIASES.get(s,s)
def fetch(url,headers=None):
 req=urllib.request.Request(url,headers=headers or {'User-Agent':'NFL-Parlay-ReadOnly-Game-ID-Audit/1.0'})
 with urllib.request.urlopen(req,timeout=40) as resp:return json.load(resp)
def main():
 base=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
 key=os.environ['SUPABASE_SERVICE_ROLE_KEY'];headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'}
 q=urllib.parse.urlencode({'select':'season,generated_at,record_count,csv_text','season':'eq.2026','limit':'1'})
 exports=fetch(base+'nfl_stat_exports?'+q,headers)
 if len(exports)!=1:raise ValueError('Missing or ambiguous 2026 export')
 rows=list(csv.DictReader(io.StringIO(exports[0]['csv_text'])))
 if int(exports[0]['record_count'])!=len(rows):raise ValueError('CSV row-count mismatch')
 games=collections.defaultdict(list)
 for r in rows:
  if r.get('game_status','').strip().upper()!='SCHEDULED':continue
  t,o=norm(r.get('team')),norm(r.get('opponent_team'))
  if r.get('home_away') not in ('HOME','AWAY') or not t or not o:continue
  home,away=(t,o) if r['home_away']=='HOME' else (o,t)
  games[(int(r['week']),away,home)].append(r)
 # Fetch all existing snapshots, not just first 1000. GET only.
 snapshots=[];offset=0
 while True:
  qs=urllib.parse.urlencode({'select':'season,week,game_id,away_team,home_team,kickoff_at,created_at','season':'eq.2026','order':'week.asc,game_id.asc','limit':'500','offset':str(offset)})
  page=fetch(base+'nfl_prediction_snapshots?'+qs,headers)
  snapshots.extend(page)
  if len(page)<500:break
  offset+=len(page)
  if offset>100000:raise ValueError('Snapshot pagination safety cap exceeded')
 existing=collections.defaultdict(list)
 for s in snapshots:existing[(int(s['week']),norm(s['away_team']),norm(s['home_team']))].append(s)
 # ESPN scoreboard returns event IDs; verify rather than infer from nflverse game_id.
 espn=collections.defaultdict(list);fetch_errors={}
 dates=sorted({str(r.get('game_date',''))[:10] for rs in games.values() for r in rs if r.get('game_date')})
 for date in dates:
  try:
   data=fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?'+urllib.parse.urlencode({'dates':date.replace('-',''),'limit':'100'}))
   for ev in data.get('events',[]):
    comps=(ev.get('competitions') or [])
    if len(comps)!=1:continue
    sides={c.get('homeAway'):norm(c.get('team',{}).get('abbreviation')) for c in comps[0].get('competitors',[])}
    if not sides.get('away') or not sides.get('home'):continue
    evdate=str(ev.get('date') or '')
    try:localdate=datetime.datetime.fromisoformat(evdate.replace('Z','+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=-5))).date().isoformat()
    except ValueError:localdate=date
    espn[(date,sides['away'],sides['home'])].append({'id':str(ev.get('id')),'kickoff_utc':evdate,'name':ev.get('name')})
  except Exception as e:fetch_errors[date]=f'{type(e).__name__}: {e}'
 results=[];counts=collections.Counter()
 for (week,away,home),rs in sorted(games.items()):
  dates0={str(r.get('game_date',''))[:10] for r in rs};times={str(r.get('game_time','')).strip() for r in rs}
  date=next(iter(dates0)) if len(dates0)==1 else None
  candidates=espn.get((date,away,home),[]) if date else []
  prior=existing.get((week,away,home),[])
  flags=[]
  if len(dates0)!=1 or len(times)!=1:flags.append('INCONSISTENT_CSV_DATE_OR_TIME')
  if date in fetch_errors:flags.append('ESPN_LOOKUP_FAILED')
  if len(candidates)!=1:flags.append('ESPN_GAME_ID_NOT_UNIQUE_OR_MISSING')
  if len(prior)>1:flags.append('MULTIPLE_EXISTING_MATCHUP_SNAPSHOTS')
  if len(prior)==1 and len(candidates)==1 and str(prior[0]['game_id'])!=candidates[0]['id']:flags.append('EXISTING_ID_DISAGREES_WITH_ESPN')
  if len(prior)==1:flags.append('EXISTING_SNAPSHOT_DO_NOT_INSERT')
  if len(prior)==0 and len(candidates)==1:flags.append('NEW_ID_REQUIRES_KICKOFF_AND_ROSTER_VALIDATION')
  for flag in flags:counts[flag]+=1
  results.append({'season':2026,'week':week,'away':away,'home':home,'csv_date':date,'csv_time':next(iter(times)) if len(times)==1 else None,'espn_game_id':candidates[0]['id'] if len(candidates)==1 else None,'espn_kickoff_utc':candidates[0]['kickoff_utc'] if len(candidates)==1 else None,'existing_game_ids':[p['game_id'] for p in prior],'flags':flags,'status':'REVIEW_REQUIRED' if flags else 'MATCHED_READ_ONLY'})
 report={'mode':'READ_ONLY_GAME_ID_AUDIT','status':'REVIEW_REQUIRED','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stats_export_generated_at':exports[0].get('generated_at'),'stats_row_count':len(rows),'scheduled_game_groups':len(results),'existing_2026_snapshot_count':len(snapshots),'espn_lookup_errors':fetch_errors,'flag_counts':dict(counts),'games':results,'limitations':['ESPN scoreboard is an external schedule source, not a roster verification','Dates are queried individually; postponed or flexed games may require manual reconciliation','Does not validate exact kickoff against CSV time zones or player eligibility','No prediction candidates are inserted; no database writes','Existing snapshots are preserved regardless of mapping result']}
 (OUT/'audit.json').write_text(json.dumps(report,indent=2))
 with (OUT/'games.csv').open('w',newline='') as f:
  fields=['season','week','away','home','csv_date','csv_time','espn_game_id','espn_kickoff_utc','existing_game_ids','flags','status'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in results:w.writerow({**r,'existing_game_ids':';'.join(map(str,r['existing_game_ids'])),'flags':';'.join(r['flags'])})
 print(json.dumps({k:report[k] for k in ('mode','status','stats_row_count','scheduled_game_groups','existing_2026_snapshot_count','flag_counts','espn_lookup_errors')},indent=2))
 print('READ ONLY: no Supabase writes. All records require review.')
if __name__=='__main__':
 try:main()
 except Exception as e:print('AUDIT FAILED:',str(e),file=sys.stderr);sys.exit(1)
