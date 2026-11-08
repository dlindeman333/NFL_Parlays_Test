#!/usr/bin/env python3
"""Consolidated read-only grading worker; produces auditable provisional results.
No write APIs or database mutations are present in this module.
"""
import datetime as dt
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from nfl_package3_live_audit import get_rows
from nfl_package4_final_evidence import fetch_scoreboard, normalize_games
from nfl_package8_market_grader import evaluate


def contract_audit(snapshots, grading):
    issues = Counter()
    candidates = []
    for snap in snapshots:
        gid = str(snap.get('game_id') or '')
        for index, pick in enumerate(snap.get('picks') or []):
            if not isinstance(pick, dict):
                issues['invalid_pick'] += 1
            elif pick.get('market') == 'player' and pick.get('stat') == 'touchdowns':
                issues['touchdown_market_semantics_unverified'] += 1
            elif pick.get('market') not in ('ml', 'player'):
                issues['unknown_market'] += 1
    for result in grading['results']:
        if result['status'] not in ('HIT', 'MISS', 'PUSH'):
            continue
        # Stable audit identity, never used to overwrite existing grades.
        key = f"{result['game_id']}/{result['pick_index']}"
        candidates.append({'audit_key': key, 'grade': result['status'],
                           'evidence': {k:v for k,v in result.items() if k not in ('game_id','pick_index','status')}})
    return {'unverified_contracts':dict(issues), 'provisional_candidates':candidates,
            'provisional_candidate_count':len(candidates)}


def build_report(snapshots, games, summary_fetch=None):
    if summary_fetch is None:
        result = evaluate(snapshots, games)
    else:
        result = evaluate(snapshots, games, summary_fetch=summary_fetch)
    result.update(contract_audit(snapshots,result))
    result['mode']='CONSOLIDATED_READ_ONLY_GRADING_WORKER'
    result['write_enabled']=False
    result['database_writes']=0
    result['official_grades_written']=0
    result['readiness']='BLOCKED_PENDING_TOUCHDOWN_DEFINITION_BACKUP_AND_EXPLICIT_WRITE_APPROVAL'
    return result


def main():
    if os.getenv('ENABLE_GRADE_WRITES', '').strip().lower() in ('true','1','yes'):
        raise RuntimeError('Grade writes are not implemented or authorized in this package')
    season=int(os.environ.get('NFL_SEASON','2026'))
    week=int(os.environ.get('NFL_WEEK','9'))
    if not (2020<=season<=2100 and 1<=week<=22):
        raise ValueError('Invalid season/week')
    url=os.environ['SUPABASE_URL']; key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    snapshots=get_rows(url,key,'nfl_prediction_snapshots',
        {'select':'season,week,game_id,home_team,away_team,picks',
         'season':f'eq.{season}','week':f'eq.{week}','limit':'1000'})
    games=normalize_games(fetch_scoreboard(season,week))
    report=build_report(snapshots,games)
    report.update({'season':season,'week':week,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    out=Path('package9-output');out.mkdir(exist_ok=True)
    (out/'grading_readiness.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('season','week','grade_counts','provisional_candidate_count','database_writes','readiness')}))

if __name__=='__main__':main()
