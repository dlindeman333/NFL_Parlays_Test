#!/usr/bin/env python3
"""Read-only pregame eligibility audit. All rows blocked pending independent roster/injury verification."""
import csv,io,json,os,sys,urllib.parse,urllib.request,datetime,collections,pathlib
from zoneinfo import ZoneInfo
OUT=pathlib.Path('phase3c3d3-report');OUT.mkdir(exist_ok=True)
UTC=datetime.timezone.utc;ET=ZoneInfo('America/New_York')
ALIASES={'JAX':'JAC','LAR':'LA','WSH':'WAS'}
def norm(x):
 x=str(x or '').strip().upper();return ALIASES.get(x,x)
def get(url,headers=None):
 req=urllib.request.Request(url,headers=headers or {'User-Agent':'NFL-Parlay-ReadOnly/1.0'})
 with urllib.request.urlopen(req,timeout=40) as resp:return json.load(resp)
def parse_csv_time(date,time):
 time=time.upper().replace(' EDT','').replace(' EST','').replace(' ET','').strip()
 for fmt in ('%H:%M','%H:%M:%S','%I:%M %p','%I:%M%p'):
  try:
   t=datetime.datetime.strptime(time,fmt).time();local=datetime.datetime.combine(datetime.date.fromisoformat(date),t,tzinfo=ET)
   if local.replace(fold=0).utcoffset()!=local.replace(fold=1).utcoffset():return None
   if local.astimezone(UTC).astimezone(ET).replace(tzinfo=None)!=local.replace(tzinfo=None):return None
   return local.astimezone(UTC)
  except ValueError:pass
 return None
def main():
 base=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
 key=os.environ['SUPABASE_SERVICE_ROLE_KEY'];hdr={'apikey':key,'Authorization':'Bearer '+key}
 q=urllib.parse.urlencode({'select':'season,generated_at,record_count,csv_text','season':'eq.2026','limit':'1'})
 exports=get(base+'nfl_stat_exports?'+q,hdr)
 if len(exports)!=1:raise ValueError('Expected one stats export')
 ex=exports[0];rows=list(csv.DictReader(io.StringIO(ex['csv_text'])))
 if int(ex['record_count'])!=len(rows):raise ValueError('Row count mismatch')
 snapshots=[];offset=0
 while True:
  q=urllib.parse.urlencode({'select':'season,week,game_id,away_team,home_team,kickoff_at','season':'eq.2026','limit':'500','offset':str(offset)})
  page=get(base+'nfl_prediction_snapshots?'+q,hdr);snapshots+=page
  if len(page)<500:break
  offset+=len(page)
  if offset>100000:raise ValueError('Pagination cap exceeded')
 existing=collections.defaultdict(list)
 for s in snapshots:existing[(int(s['week']),norm(s['away_team']),norm(s['home_team']))].append(s)
 groups=collections.defaultdict(list)
 for r in rows:
  if r.get('game_status','').strip().upper()!='SCHEDULED':continue
  team,opp=norm(r.get('team')),norm(r.get('opponent_team'))
  if r.get('home_away') not in ('HOME','AWAY') or not team or not opp:continue
  home,away=(team,opp) if r['home_away']=='HOME' else (opp,team)
  groups[(int(r['week']),away,home)].append(r)
 # Build same preview candidate pool as Phase 3C2 (read only).
 import phase3c2_preview
 phase3c2_preview.preview()
 preview=json.loads(pathlib.Path('phase3c2-report/preview.json').read_text())
 preds=collections.defaultdict(list)
 for p in preview['predictions']:
  a,h=p['game'].split(' @ ');preds[(int(p['week']),norm(a),norm(h))].append(p)
 now=datetime.datetime.now(UTC)
 generated=datetime.datetime.fromisoformat(ex['generated_at'].replace('Z','+00:00'))
 fresh=datetime.timedelta(0)<=now-generated<=datetime.timedelta(hours=72)
 dates=sorted({str(r.get('game_date',''))[:10] for rs in groups.values() for r in rs if r.get('game_date')})
 espn=collections.defaultdict(list);errors={}
 for d in dates:
  try:
   url='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?'+urllib.parse.urlencode({'dates':d.replace('-',''),'limit':'100'})
   data=get(url)
   for event in data.get('events',[]):
    comps=event.get('competitions') or []
    if len(comps)!=1:continue
    sides={c.get('homeAway'):norm(c.get('team',{}).get('abbreviation')) for c in comps[0].get('competitors',[])}
    if sides.get('away') and sides.get('home'):
     espn[(d,sides['away'],sides['home'])].append(event)
  except Exception as e:errors[d]=str(e)
 results=[];counts=collections.Counter()
 for (week,away,home),rs in sorted(groups.items()):
  flags=[];dates0={str(r.get('game_date',''))[:10] for r in rs};times={str(r.get('game_time','')).strip() for r in rs}
  date=next(iter(dates0)) if len(dates0)==1 else None
  time=next(iter(times)) if len(times)==1 else None
  if not date or not time:flags.append('INCONSISTENT_CSV_KICKOFF')
  csvkick=parse_csv_time(date,time) if date and time else None
  if not csvkick:flags.append('CSV_KICKOFF_UNPARSEABLE')
  events=espn.get((date,away,home),[]) if date else []
  if date in errors:flags.append('ESPN_FETCH_ERROR')
  if len(events)!=1:flags.append('ESPN_EVENT_NOT_UNIQUE_OR_MISSING')
  event=events[0] if len(events)==1 else None
  ekick=None
  if event:
   try:ekick=datetime.datetime.fromisoformat(event['date'].replace('Z','+00:00'))
   except (ValueError,KeyError):flags.append('ESPN_KICKOFF_UNPARSEABLE')
  if ekick:
   local=ekick.astimezone(ET)
   if local.hour==0 and local.minute==0:flags.append('MIDNIGHT_PLACEHOLDER_REVIEW')
   if csvkick and abs((ekick-csvkick).total_seconds())>60:flags.append('KICKOFF_DISAGREEMENT')
   if ekick<=now+datetime.timedelta(minutes=60):flags.append('INSUFFICIENT_TIME_BEFORE_KICKOFF')
   if ekick>now+datetime.timedelta(days=7):flags.append('OUTSIDE_7_DAY_WINDOW')
  if not fresh:flags.append('STATS_EXPORT_STALE')
  prior=existing.get((week,away,home),[])
  if prior:flags.append('EXISTING_SNAPSHOT_DO_NOT_INSERT')
  if len(prior)>1:flags.append('MULTIPLE_SNAPSHOTS_FOR_MATCHUP')
  if prior and event and any(str(s['game_id'])!=str(event['id']) for s in prior):flags.append('EXISTING_GAME_ID_MISMATCH')
  pp=preds.get((week,away,home),[])
  if not pp:flags.append('NO_PREVIEW_PREDICTIONS')
  if any(int(p['historical_games'])<3 for p in pp):flags.append('PLAYER_HISTORY_BELOW_3')
  # We do not have an independently verified roster/injury feed. Never certify eligibility.
  flags.append('ROSTER_AND_INJURY_UNVERIFIED')
  for f in set(flags):counts[f]+=1
  results.append({'week':week,'away':away,'home':home,'csv_date':date,'csv_time':time,'csv_kickoff_utc':csvkick.isoformat() if csvkick else None,'espn_game_id':str(event['id']) if event else None,'espn_kickoff_utc':ekick.isoformat() if ekick else None,'existing_snapshot_count':len(prior),'preview_prediction_count':len(pp),'flags':sorted(set(flags)),'status':'BLOCKED_NO_WRITES'})
 report={'mode':'READ_ONLY_FINAL_ELIGIBILITY_AUDIT','status':'REVIEW_REQUIRED_NO_WRITES','generated_utc':now.isoformat(),'stats_export_generated_at':ex['generated_at'],'stats_export_fresh':fresh,'games_evaluated':len(results),'preview_predictions':len(preview['predictions']),'existing_snapshot_count':len(snapshots),'eligible_for_insert':0,'blocker_counts':dict(counts),'external_lookup_errors':errors,'games':results,'limitations':['No authoritative roster or injury verification: all games remain blocked','ESPN midnight local timestamps treated as unconfirmed','Independent roster validation and existing picks schema compatibility still required','No INSERT, UPDATE, UPSERT or DELETE operations; no snapshots created']}
 (OUT/'audit.json').write_text(json.dumps(report,indent=2))
 with (OUT/'games.csv').open('w',newline='') as f:
  fields=['week','away','home','csv_date','csv_time','csv_kickoff_utc','espn_game_id','espn_kickoff_utc','existing_snapshot_count','preview_prediction_count','flags','status'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in results:w.writerow({**r,'flags':';'.join(r['flags'])})
 print(json.dumps({k:v for k,v in report.items() if k not in ('games','limitations')},indent=2));print('READ ONLY: no snapshots written.')
if __name__=='__main__':
 try:main()
 except Exception as exc:print('AUDIT FAILED:',str(exc),file=sys.stderr);sys.exit(1)
