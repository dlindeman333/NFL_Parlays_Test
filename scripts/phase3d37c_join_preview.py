#!/usr/bin/env python3
"""Live roster + Supabase stats joined preview. GET-only, never writes or authenticates predictions."""
import argparse,csv,io,json,os,sys
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from phase3d36c_supabase_stats import fetch_latest,MAX_CSV_BYTES
from phase3d36b_stats_candidates import candidate,number
from phase3d37b_roster_match import BASE,fetch,teams,athletes,games,verify,parse_dt

def as_utc(s):
    if not s:return None
    try:return parse_dt(s).astimezone(timezone.utc)
    except (TypeError,ValueError):return None

def join(rows,matches,team_abbr,season,week,export_time,now):
    by_id={m['player_id']:m for m in matches if m['status']=='matched'}
    best={}; exclusions=Counter(); export_dt=as_utc(export_time)
    for row in rows:
        c,reason=candidate(row,season)
        if reason:exclusions[reason]+=1;continue
        pid=c['player_id']; m=by_id.get(pid)
        if not m:exclusions['unmatched_roster_or_game']+=1;continue
        if str(row.get('team','')).strip().upper()!=team_abbr.get(m['team_id'],'').upper():
            exclusions['team_mismatch']+=1;continue
        if str(row.get('next_opponent','')).strip().upper()!=team_abbr.get(m['opponent_team_id'],'').upper():
            exclusions['opponent_mismatch']+=1;continue
        kickoff=as_utc(m['kickoff_at'])
        if not kickoff or kickoff<=now:exclusions['game_started']+=1;continue
        if not export_dt or export_dt>=kickoff or export_dt>now:
            exclusions['export_not_point_in_time']+=1;continue
        row_week=number(row.get('week'))
        if row_week is None or row_week>=week:
            exclusions['source_week_not_prior']+=1;continue
        # If provided, reject row's game date on or after target kickoff.
        historical=as_utc(row.get('game_date'))
        if historical and historical>=kickoff:
            exclusions['historical_date_not_prior']+=1;continue
        # Only use completed-game records. Missing/unknown status is not sufficient.
        if str(row.get('game_status','')).strip().lower() not in ('final','completed','complete','post'):
            exclusions['unverified_completed_game']+=1;continue
        existing=best.get(pid)
        if existing is None or row_week>existing[0]:
            best[pid]=(row_week,{'player_id':pid,'player_name':c['name'],'team':team_abbr[m['team_id']],
                'opponent':team_abbr[m['opponent_team_id']],'game_id':m['game_id'],
                'kickoff_at':m['kickoff_at'],'source_week':int(row_week),'projections':c['projections']})
    return [v[1] for v in sorted(best.values(),key=lambda v:(v[1]['game_id'],v[1]['player_name']))],dict(exclusions)

def run(season,week):
    now=datetime.now(timezone.utc)
    report={'phase':'3D37C','mode':'READ_ONLY','run_at_utc':now.isoformat(),'season':season,'week':week,
        'database_writes':0,'authentic_snapshots_created':0,'grades_created':0,'status':'error',
        'limitations':['Baseline projections only; no odds, defensive adjustment, calibrated confidence or grading',
        'ESPN roster is current, not a historical point-in-time roster',
        'Export creation time is not proof that every source statistic was available before kickoff',
        'No predictions may be saved based solely on this preview']}
    try:
        team_list=teams(fetch(BASE+'/teams?limit=50'))
        if len(team_list)!=32:raise ValueError('incomplete_team_list')
        abbr={str(t['id']):str(t.get('abbreviation','')).upper() for t in team_list}
        if any(not a for a in abbr.values()):raise ValueError('missing_team_abbreviation')
        roster=defaultdict(list)
        for t in team_list:
            tid=str(t['id'])
            for a in athletes(fetch(BASE+f'/teams/{tid}/roster')):
                if a.get('id'):roster[str(a['id'])].append({'team_id':tid})
        schedule=games(fetch(BASE+f'/scoreboard?dates={season}&week={week}&seasontype=2&limit=1000'))
        if not schedule:raise ValueError('empty_schedule')
        matches=verify(roster,schedule,now)
        export=fetch_latest(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],season)
        if not export or not export.get('csv_text'):raise ValueError('missing_statistics_export')
        raw=export['csv_text']
        if len(raw.encode('utf-8'))>MAX_CSV_BYTES:raise ValueError('csv_too_large')
        reader=csv.DictReader(io.StringIO(raw,newline=''))
        required={'season','week','player_id','name','team','next_opponent','games_played_to_date','game_status'}
        if not required.issubset(reader.fieldnames or []):raise ValueError('missing_required_columns')
        rows=list(reader)
        previews,excluded=join(rows,matches,abbr,season,week,export.get('generated_at'),now)
        report.update(status='ok',roster_players=len(roster),roster_matched=sum(x['status']=='matched' for x in matches),
            games_found=len(schedule),stats_rows=len(rows),export_generated_at=export.get('generated_at'),
            matched_projection_players=len(previews),exclusions=excluded,
            sample_projections=previews[:20],sample_limit=20,report_truncated=len(previews)>20)
    except Exception as exc:
        report['error_type']=type(exc).__name__
        report['error_stage']='live_join';report['status']='error'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int,required=True);p.add_argument('--output',default='phase3d37c_report.json');args=p.parse_args()
    if not 1<=args.week<=18 or not 2020<=args.season<=2100:sys.exit('Invalid season/week')
    result=run(args.season,args.week)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result.get(k) for k in ('status','roster_matched','matched_projection_players','exclusions','database_writes','error_type')}))
    if result['status']!='ok':sys.exit(1)
