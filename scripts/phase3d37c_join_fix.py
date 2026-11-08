#!/usr/bin/env python3
"""Read-only staged roster/statistics join. Fail closed; no synthetic identity matching."""
import argparse,csv,io,json,os,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from phase3d36c_supabase_stats import fetch_latest,MAX_CSV_BYTES
from phase3d36b_stats_candidates import candidate,number
from phase3d37b_roster_match import BASE,fetch,teams,athletes,games,verify,parse_dt

def norm_id(value):
    s=str(value or '').strip()
    m=re.fullmatch(r'(?:https?://[^/]+/[^?#]*/)?(\d+)(?:\.0)?',s)
    return m.group(1) if m else s

def utc(value):
    try:return parse_dt(value).astimezone(timezone.utc) if value else None
    except (ValueError,TypeError,AttributeError):return None

def assess(rows,matches,abbr,season,week,export_time,now):
    by_id={norm_id(m['player_id']):m for m in matches if m['status']=='matched'}
    all_roster={norm_id(m['player_id']) for m in matches}
    counts=Counter(); samples=defaultdict(list); best={}
    exp=utc(export_time)
    for row in rows:
        c,reason=candidate(row,season)
        if reason: counts[reason]+=1;continue
        counts['eligible_stat_rows']+=1
        pid=norm_id(c['player_id'])
        m=by_id.get(pid)
        if not m:
            reason='id_absent_from_roster' if pid not in all_roster else 'player_has_no_upcoming_game'
        elif str(row.get('team','')).strip().upper()!=abbr.get(m['team_id'],'').upper():
            reason='team_mismatch'
        elif str(row.get('next_opponent','')).strip().upper()!=abbr.get(m['opponent_team_id'],'').upper():
            reason='opponent_mismatch'
        elif not utc(m['kickoff_at']) or utc(m['kickoff_at'])<=now:
            reason='game_started'
        elif not exp or exp>=utc(m['kickoff_at']) or exp>now:
            reason='export_not_point_in_time'
        elif number(row.get('week')) is None or number(row.get('week'))>=week:
            reason='source_week_not_prior'
        elif utc(row.get('game_date')) and utc(row.get('game_date'))>=utc(m['kickoff_at']):
            reason='historical_date_not_prior'
        elif str(row.get('game_status','')).strip().lower() not in ('final','completed','complete','post'):
            reason='unverified_completed_game'
        else:reason='accepted'
        counts[reason]+=1
        if reason!='accepted':
            if len(samples[reason])<3:
                # Diagnostic identifiers only; never include credentials or raw CSV.
                samples[reason].append({'player_id':pid,'stats_team':row.get('team',''), 'stats_opponent':row.get('next_opponent',''),
                   'roster_team':abbr.get(m['team_id']) if m else None,'roster_opponent':abbr.get(m['opponent_team_id']) if m else None,
                   'source_week':row.get('week'),'game_status':row.get('game_status')})
            continue
        rw=number(row.get('week'))
        if pid not in best or rw>best[pid][0]:
            best[pid]=(rw,{'player_id':pid,'player_name':c['name'],'team':abbr[m['team_id']],
              'opponent':abbr[m['opponent_team_id']],'game_id':m['game_id'],'kickoff_at':m['kickoff_at'],
              'source_week':int(rw),'projections':c['projections']})
    return {'stage_counts':dict(counts),'diagnostic_samples':dict(samples),'matched_projection_players':len(best),
            'sample_projections':[x[1] for x in list(best.values())[:20]]}

def run(season,week):
    now=datetime.now(timezone.utc)
    report={'phase':'3D37C-fix','mode':'READ_ONLY','run_at_utc':now.isoformat(),'season':season,'week':week,
      'status':'error','database_writes':0,'snapshots_created':0,'grades_created':0,
      'warning':'Current roster is not a historical roster. This is a diagnostic projection preview, not an authentic pregame prediction.'}
    try:
        ts=teams(fetch(BASE+'/teams?limit=50'))
        if len(ts)!=32:raise ValueError('incomplete_team_list')
        abbr={str(t['id']):str(t.get('abbreviation','')).upper() for t in ts}
        roster=defaultdict(list)
        for t in ts:
            for a in athletes(fetch(BASE+f"/teams/{t['id']}/roster")):
                if a.get('id'):roster[norm_id(a['id'])].append({'team_id':str(t['id'])})
        schedule=games(fetch(BASE+f'/scoreboard?dates={season}&week={week}&seasontype=2&limit=1000'))
        if not schedule:raise ValueError('empty_schedule')
        matches=verify(roster,schedule,now)
        export=fetch_latest(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],season)
        if not export or not export.get('csv_text'):raise ValueError('missing_stats_export')
        raw=export['csv_text']
        if len(raw.encode('utf-8'))>MAX_CSV_BYTES:raise ValueError('csv_too_large')
        reader=csv.DictReader(io.StringIO(raw,newline=''))
        needed={'season','week','player_id','name','team','next_opponent','games_played_to_date','game_status'}
        if not needed.issubset(reader.fieldnames or []):raise ValueError('missing_columns')
        rows=list(reader)
        result=assess(rows,matches,abbr,season,week,export.get('generated_at'),now)
        report.update(status='ok',roster_players=len(roster),roster_matched=sum(m['status']=='matched' for m in matches),
          games_found=len(schedule),stats_rows=len(rows),export_generated_at=export.get('generated_at'),**result)
    except Exception as exc:
        report['error_type']=type(exc).__name__
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int,default=10);p.add_argument('--output',default='phase3d37c_fix_report.json');a=p.parse_args()
    if not 1<=a.week<=18:raise SystemExit('Invalid week')
    r=run(a.season,a.week);Path(a.output).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:r.get(k) for k in ('status','matched_projection_players','stage_counts','database_writes','error_type')}))
    if r['status']!='ok':raise SystemExit(1)
