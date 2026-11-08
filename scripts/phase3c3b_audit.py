#!/usr/bin/env python3
"""Read-only Phase 3C-3B audit. Never issues database mutations."""
import csv,io,json,os,urllib.request,urllib.parse,collections,datetime,pathlib,sys
OUT=pathlib.Path('phase3c3b-report');OUT.mkdir(exist_ok=True)
ALIASES={'JAX':'JAC','JAC':'JAC','LAR':'LA','LA':'LA','WSH':'WAS','WAS':'WAS'}
def norm(s):
 s=(s or '').strip().upper();return ALIASES.get(s,s)
def get(url,headers=None):
 req=urllib.request.Request(url,headers=headers or {'User-Agent':'NFL-Parlay-ReadOnly-Audit/1.0'})
 with urllib.request.urlopen(req,timeout=40) as resp:return resp.read()
def main():
 base=os.environ['SUPABASE_URL'].rstrip('/')+'/rest/v1/'
 key=os.environ['SUPABASE_SERVICE_ROLE_KEY'];headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'}
 q=urllib.parse.urlencode({'select':'season,generated_at,record_count,csv_text','season':'eq.2026','limit':'1'})
 data=json.loads(get(base+'nfl_stat_exports?'+q,headers))
 if len(data)!=1:raise ValueError('2026 stats export missing or ambiguous')
 rows=list(csv.DictReader(io.StringIO(data[0]['csv_text'])))
 if int(data[0]['record_count'])!=len(rows):raise ValueError('Stats row count mismatch')
 games=collections.defaultdict(list);players=collections.defaultdict(set)
 for r in rows:
  team=norm(r.get('team'));opp=norm(r.get('opponent_team'));week=r.get('week','').strip();status=r.get('game_status','').strip().upper()
  if status=='COMPLETED' and r.get('player_id'):players[(team,r.get('player','').lower())].add(r['player_id'])
  if status!='SCHEDULED' or not week or r.get('home_away') not in ('HOME','AWAY'):continue
  home,away=(team,opp) if r['home_away']=='HOME' else (opp,team)
  games[(week,away,home)].append(r)
 # NFLverse public historical schedule, independent of local CSV.
 schedule_url='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
 schedule=[];schedule_error=None
 try:
  schedule=list(csv.DictReader(io.StringIO(get(schedule_url).decode('utf-8-sig'))))
 except Exception as e:schedule_error=f'{type(e).__name__}: {e}'
 # Match by teams and date; require exactly one schedule match. Never silently change weeks.
 index=collections.defaultdict(list)
 for r in schedule:
  if str(r.get('season'))!='2026':continue
  home=norm(r.get('home_team'));away=norm(r.get('away_team'));date=(r.get('gameday') or r.get('game_date') or '')[:10]
  if date:index[(away,home,date)].append(r)
 findings=[];counts=collections.Counter()
 for (week,away,home),rs in sorted(games.items()):
  dates={str(r.get('game_date',''))[:10] for r in rs};times={str(r.get('game_time','')) for r in rs}
  date=next(iter(dates)) if len(dates)==1 else None
  match=index.get((away,home,date),[]) if date else []
  flags=[]
  if len(dates)!=1 or len(times)!=1:flags.append('INCONSISTENT_CSV_KICKOFF')
  if not schedule:flags.append('EXTERNAL_SCHEDULE_UNAVAILABLE')
  elif len(match)!=1:flags.append('NO_UNIQUE_EXTERNAL_SCHEDULE_MATCH')
  elif str(match[0].get('week'))!=week:flags.append('WEEK_MISMATCH')
  if away==home or not away or not home:flags.append('INVALID_TEAM_PAIR')
  for f in flags:counts[f]+=1
  findings.append({'csv_week':week,'away':away,'home':home,'csv_date':date,'csv_time':next(iter(times)) if len(times)==1 else None,'external_week':match[0].get('week') if len(match)==1 else None,'external_game_id':match[0].get('game_id') if len(match)==1 else None,'flags':flags,'scheduled_csv_rows':len(rs)})
 # Read-only snapshot metadata; do not include private rows in report.
 table_status={}
 for table in ('nfl_prediction_snapshots','nfl_prediction_grades','nfl_user_prediction_tracking'):
  try:
   req_headers={**headers,'Prefer':'count=exact'}
   req=urllib.request.Request(base+table+'?select=season&limit=0',headers=req_headers)
   with urllib.request.urlopen(req,timeout=30) as resp:
    table_status[table]={'accessible':True,'content_range':resp.headers.get('Content-Range')}
  except Exception as e:table_status[table]={'accessible':False,'error':str(e)[:240]}
 try:
  openapi=json.loads(get(base, {**headers,'Accept':'application/openapi+json'}))
  defs=openapi.get('definitions',{})
  snap=defs.get('nfl_prediction_snapshots',{})
  schema={'properties':list(snap.get('properties',{})),'required':snap.get('required',[]),'primary_key':snap.get('primary_key'),'description':snap.get('description')}
 except Exception as e:schema={'error':str(e)[:240]}
 duplicate_names=[{'team':team,'player':name,'player_ids':sorted(ids)} for (team,name),ids in players.items() if len(ids)>1]
 status='PASS' if schedule and not counts and findings and schema.get('properties') else 'REVIEW_REQUIRED'
 report={'mode':'READ_ONLY_PHASE3C3B_AUDIT','status':status,'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_export_generated_at':data[0]['generated_at'],'csv_rows':len(rows),'schedule_source':schedule_url,'external_schedule_error':schedule_error,'scheduled_games':len(findings),'issue_counts':dict(counts),'snapshot_table_counts':table_status,'snapshot_schema_openapi':schema,'players_with_multiple_ids':duplicate_names[:100],'games':findings,'limitations':['External schedule matching uses date and normalized team codes; games with changed dates or neutral sites need manual review','No live roster or injury source is checked','OpenAPI metadata is not proof of unique constraints, RLS, or database triggers','No pregame predictions, snapshots, or database writes']}
 (OUT/'audit.json').write_text(json.dumps(report,indent=2))
 with (OUT/'games.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['csv_week','away','home','csv_date','csv_time','external_week','external_game_id','flags','scheduled_csv_rows']);w.writeheader()
  for g in findings:w.writerow({**g,'flags':';'.join(g['flags'])})
 print(json.dumps({k:report[k] for k in ('mode','status','csv_rows','scheduled_games','issue_counts','external_schedule_error','snapshot_table_counts')},indent=2))
 print('READ ONLY: No Supabase writes.')
 # Review required is a normal diagnostic outcome; fail only on unexpected errors.
if __name__=='__main__':
 try:main()
 except Exception as e:print('AUDIT ERROR:',str(e),file=sys.stderr);sys.exit(1)
