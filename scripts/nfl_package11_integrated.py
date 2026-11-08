#!/usr/bin/env python3
"""Integrated scheduled grading and immutable proposal manifest. Read-only."""
import datetime as dt
import json
import os
from pathlib import Path
from nfl_package10_scheduled_worker import resolve_week
from nfl_package3_live_audit import get_rows
from nfl_package4_final_evidence import fetch_scoreboard, normalize_games
from nfl_package9_consolidated_worker import build_report
from nfl_package11_grade_plan import build_plan

def run(season, week, fetch_rows=get_rows, fetch_games=fetch_scoreboard, grade=build_report):
    url, key = os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY']
    snaps = fetch_rows(url,key,'nfl_prediction_snapshots',{'select':'season,week,game_id,home_team,away_team,picks','season':f'eq.{season}','week':f'eq.{week}','limit':'1000'})
    if len(snaps) >= 1000: raise ValueError('Snapshot list potentially truncated')
    games = normalize_games(fetch_games(season,week))
    report = grade(snaps, games)
    plan = build_plan(snaps,report,season,week)
    return {'season':season,'week':week,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'snapshot_count':len(snaps),'game_count':len(games),
            'grading':report,'grade_plan':plan,'database_writes':0,
            'injury_sync_enabled':False,'pregame_prediction_writes_enabled':False}

def main():
    for k in ('ENABLE_GRADE_WRITES','ENABLE_PREDICTION_WRITES','ENABLE_INJURY_WRITES'):
        if os.getenv(k,'').lower() in ('true','yes','1'):
            raise RuntimeError(f'{k} is forbidden in this package')
    season,week=resolve_week(os.environ)
    result=run(season,week)
    out=Path('package11-output');out.mkdir(exist_ok=True)
    (out/'integrated_grade_plan.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'season':season,'week':week,'snapshots':result['snapshot_count'],
                      'grade_proposals':result['grade_plan']['candidate_count'],'database_writes':0}))
if __name__=='__main__':main()
