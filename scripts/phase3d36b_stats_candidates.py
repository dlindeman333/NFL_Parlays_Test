#!/usr/bin/env python3
"""Read-only NFL player-stat candidate preview. Never creates snapshots or writes to Supabase."""
import csv, datetime as dt, json, os, re, urllib.parse, urllib.request
from pathlib import Path

METRICS = ('pass_yards','rush_yards','rec_yards','receptions','pass_attempts','rush_attempts','targets')
REQUIRED = ('season','week','player_id','name','team','next_opponent','games_played_to_date')

def number(value):
    try:
        if value is None or str(value).strip() == '': return None
        n=float(value)
        return n if n == n and abs(n) < 1e8 else None
    except (ValueError,TypeError): return None

def candidate(row, season=2026, minimum_games=3):
    if any(not str(row.get(k,'')).strip() for k in REQUIRED): return None,'missing_required'
    if str(row['season']) != str(season): return None,'wrong_season'
    if str(row.get('is_future','')).lower() in ('true','1','yes'): return None,'future_row'
    if str(row.get('game_status','')).lower() in ('scheduled','in progress','live','future'): return None,'not_completed'
    games=number(row['games_played_to_date'])
    if games is None or games < minimum_games: return None,'insufficient_history'
    if not str(row['next_opponent']).strip(): return None,'no_next_opponent'
    results=[]
    for metric in METRICS:
        recent=number(row.get(metric+'_last3_avg'))
        season_avg=number(row.get(metric+'_season_avg'))
        if recent is None or season_avg is None or recent < 0 or season_avg < 0: continue
        projection=round(.6*recent+.4*season_avg,1)
        results.append({'metric':metric,'projection':projection,'last3_avg':recent,'season_avg':season_avg,
                        'method':'0.60 x last3 + 0.40 x season average',
                        'odds_adjusted':False,'opponent_adjusted':False,'confidence_calibrated':False})
    if not results:return None,'missing_averages'
    return {'player_id':str(row['player_id']),'name':row['name'],'team':row['team'],
            'next_opponent':row['next_opponent'],'season':season,'source_week':row['week'],
            'games_played':int(games),'projections':results},None

def preview(rows, season=2026):
    latest={}; rejected={}; total=0
    for row in rows:
        total+=1
        c,reason=candidate(row,season)
        if reason: rejected[reason]=rejected.get(reason,0)+1;continue
        key=c['player_id']; week=number(c['source_week']) or -1
        if key not in latest or week > latest[key][0]:latest[key]=(week,c)
    return {'input_rows':total,'eligible_unique_players':len(latest),'rejected_reasons':rejected,
            'candidates':[x[1] for x in sorted(latest.values(),key=lambda x:(x[1]['team'],x[1]['name']))][:50],
            'report_truncated':len(latest)>50}

def inspect_supabase():
    base=os.getenv('SUPABASE_URL','').rstrip('/'); key=os.getenv('SUPABASE_SERVICE_ROLE_KEY','')
    if not base or not key:return {'status':'skipped_missing_secrets'}
    parsed=urllib.parse.urlsplit(base)
    if parsed.scheme!='https' or not re.fullmatch(r'[a-z0-9-]+\.supabase\.co',parsed.hostname or '') or parsed.path or parsed.query:
        return {'status':'invalid_project_url'}
    url=base+'/rest/v1/nfl_stat_exports?select=*&limit=1'
    req=urllib.request.Request(url,headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json','Prefer':'count=exact'},method='GET')
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            rows=json.load(response)
            content_range=response.headers.get('Content-Range','')
        return {'status':'ok','row_count_header':content_range.rsplit('/',1)[-1] if '/' in content_range else None,
                'sample_column_names':sorted(rows[0].keys()) if rows else [],'sample_row_exported':False}
    except Exception as e:
        return {'status':'error','error_type':type(e).__name__}

def main():
    path=Path(os.getenv('STATS_CSV','data/nfl_player_stats_2026.csv'))
    report={'phase':'3D36B','mode':'READ_ONLY','writes':0,'snapshots_created':0,'grades_created':0,
            'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'supabase_stat_exports':inspect_supabase(),'csv_path':str(path),
            'limitations':['Illustrative statistical projections, not authenticated AI prediction snapshots',
                           'No opponent defense adjustment or sportsbook line/odds integration',
                           'CSV must contain only completed-game historical rows and valid pregame next-opponent information',
                           'No historical snapshot backfill; no database writes']}
    if path.is_file():
        with path.open(newline='',encoding='utf-8-sig') as f:
            reader=csv.DictReader(f)
            report['csv_missing_required_columns']=sorted(set(REQUIRED)-set(reader.fieldnames or []))
            report['preview']=preview(reader) if not report['csv_missing_required_columns'] else None
    else:
        report['csv_status']='not_found';report['preview']=None
    Path('phase3d36b_stats_preview.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'supabase':report['supabase_stat_exports']['status'],'csv_found':path.is_file(),
                      'eligible_players':(report['preview'] or {}).get('eligible_unique_players',0),'writes':0}))
    if report['supabase_stat_exports']['status'] in ('error','invalid_project_url'):raise SystemExit(1)

if __name__=='__main__':main()
