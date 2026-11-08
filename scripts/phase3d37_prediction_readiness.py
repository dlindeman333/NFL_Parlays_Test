#!/usr/bin/env python3
"""Read-only pregame candidate readiness; never saves snapshots or grades."""
import csv, datetime as dt, io, json, os, urllib.parse, urllib.request
from pathlib import Path
from phase3d36c_supabase_stats import fetch_latest
from phase3d36b_stats_candidates import candidate

UTC=dt.timezone.utc

def parse_time(value):
    if not value: return None
    try:
        parsed=dt.datetime.fromisoformat(str(value).strip().replace('Z','+00:00'))
        if parsed.tzinfo is None: return None
        return parsed.astimezone(UTC)
    except ValueError: return None

def choose_rows(csv_text, now, export_time, season=2026):
    """Fail closed on point-in-time ambiguity; do not mistake source rows for true predictions."""
    if not export_time or export_time>now: return {'status':'blocked_export_timestamp','eligible':0,'reasons':{'export_timestamp':1},'samples':[]}
    rows=csv.DictReader(io.StringIO(csv_text,newline=''))
    reasons={}; chosen={}
    for row in rows:
        c, reason=candidate(row,season)
        if reason:
            reasons[reason]=reasons.get(reason,0)+1;continue
        # Row date is a game-level date, not necessarily the last known stat update.
        # Require unambiguous upcoming matchup and future kickoff from trusted schedule.
        # A date alone is insufficient to authenticate pregame availability.
        if not str(row.get('next_game_date','')).strip():
            reasons['missing_next_game_date']=reasons.get('missing_next_game_date',0)+1;continue
        if str(row.get('future_team_assignment_provisional','')).lower() in ('true','1','yes'):
            reasons['provisional_team_assignment']=reasons.get('provisional_team_assignment',0)+1;continue
        key=(c['player_id'],c['next_opponent'])
        week=int(float(c['source_week']))
        if key not in chosen or week>chosen[key][0]: chosen[key]=(week,c)
    samples=[]
    for _, c in sorted(chosen.values(),key=lambda x:(x[1]['team'],x[1]['name']))[:12]:
        samples.append({'player_id':c['player_id'],'name':c['name'],'team':c['team'],'next_opponent':c['next_opponent'],
                        'projections':[{ 'metric':p['metric'],'baseline':p['projection']} for p in c['projections'][:4]]})
    return {'status':'review_only_requires_schedule_and_asof_validation','eligible':len(chosen),'reasons':reasons,'samples':samples,
            'snapshot_ready':False,'limitations':['Upcoming kickoff not verified against authoritative event ID',
            'Historical feature values not independently verified as of kickoff',
            'No defensive adjustment, calibrated probability, injury gating, or sportsbook lines']}

def main():
    report={'phase':'3D37A','mode':'READ_ONLY','writes':0,'snapshots_created':0,'grades_created':0,
            'generated_at_utc':dt.datetime.now(UTC).isoformat(),
            'automation_status':'NOT_ENABLED','prediction_snapshot_ready':False}
    try:
        now=dt.datetime.now(UTC)
        url=os.environ['SUPABASE_URL'].rstrip('/')
        key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
        season=int(os.environ.get('NFL_SEASON','2026'))
        export=fetch_latest(url,key,season)
        if not export: report['result']={'status':'no_export'}
        elif not isinstance(export.get('csv_text'),str): report['result']={'status':'missing_csv_text'}
        else:
            report['source']={'season':season,'generated_at':export.get('generated_at'), 'record_count':export.get('record_count')}
            report['result']=choose_rows(export['csv_text'],now,parse_time(export.get('generated_at')),season)
    except Exception as exc:
        report['result']={'status':'error','type':type(exc).__name__}
    Path('phase3d37a_readiness.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['result']['status'],'candidates':report['result'].get('eligible',0),'writes':0}))
    if report['result']['status'] in ('error','no_export','missing_csv_text','blocked_export_timestamp'): raise SystemExit(1)

if __name__=='__main__':main()
