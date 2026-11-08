#!/usr/bin/env python3
"""Scheduled read-only current-week grading, with evidence and operational health report.
Does not create snapshots, grade rows, injuries, or write to Supabase.
"""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
from nfl_package3_live_audit import get_rows
from nfl_package4_final_evidence import fetch_scoreboard, normalize_games
from nfl_package9_consolidated_worker import build_report

CURRENT_SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'

def select_week(payload):
    league = ((payload.get('leagues') or [{}])[0])
    season = league.get('season') or {}
    week = league.get('calendarType')  # not used; ESPN's week number is in payload.week.number
    w = (payload.get('week') or {}).get('number')
    y = season.get('year')
    season_type = (season.get('type') or {}).get('type') if isinstance(season.get('type'),dict) else season.get('type')
    if season_type is not None and str(season_type) != '2':
        raise ValueError('Current ESPN season is not regular season; manual season/week required')
    if not isinstance(y,int) or not isinstance(w,int) or not (2020 <= y <= 2100 and 1 <= w <= 18):
        raise ValueError('ESPN current scoreboard did not provide a valid regular-season year/week')
    return y,w

def fetch_current_week():
    req=urllib.request.Request(CURRENT_SCOREBOARD,headers={'User-Agent':'NFL-Parlay-Scheduled-ReadOnly/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=35) as resp:
        raw=resp.read(2_000_001)
    if len(raw)>2_000_000: raise ValueError('ESPN current scoreboard response too large')
    return select_week(json.loads(raw))

def resolve_week(env, current_week_fetch=fetch_current_week):
    s=(env.get('NFL_SEASON') or '').strip(); w=(env.get('NFL_WEEK') or '').strip()
    if bool(s)!=bool(w): raise ValueError('Set both NFL_SEASON and NFL_WEEK, or neither')
    if s and w:
        season,week=int(s),int(w)
        if not 2020<=season<=2100 or not 1<=week<=22: raise ValueError('Invalid season/week')
        return season,week
    return current_week_fetch()

def run(season,week,fetch_rows=get_rows,scoreboard_fetch=fetch_scoreboard):
    url=os.environ['SUPABASE_URL']; key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    snapshots=fetch_rows(url,key,'nfl_prediction_snapshots',{'select':'season,week,game_id,home_team,away_team,picks','season':f'eq.{season}','week':f'eq.{week}','limit':'1000'})
    if len(snapshots)==1000: raise ValueError('Snapshot query may be truncated; refusing incomplete report')
    games=normalize_games(scoreboard_fetch(season,week))
    report=build_report(snapshots,games)
    report.update({'season':season,'week':week,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                   'snapshot_count':len(snapshots),'scoreboard_game_count':len(games),
                   'schedule_enabled':True,'grade_write_enabled':False,'prediction_write_enabled':False,
                   'injury_sync_enabled':False,'database_writes':0,
                   'remaining_blockers':['Touchdown semantics must be confirmed against actual saved app contract',
                       'Official grade table schema and conflict policy must be verified before implementing writes',
                       'Backup/restore and explicit write approval required',
                       'Injury and pregame prediction jobs are not implemented by this package']})
    return report

def main():
    if os.getenv('ENABLE_GRADE_WRITES','').lower() in ('1','true','yes'):
        raise RuntimeError('Writes forbidden: this package is read-only')
    season,week=resolve_week(os.environ)
    report=run(season,week)
    out=Path('package10-output');out.mkdir(exist_ok=True)
    (out/'scheduled_worker_report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('season','week','snapshot_count','grade_counts','database_writes','readiness')}))
if __name__=='__main__': main()
