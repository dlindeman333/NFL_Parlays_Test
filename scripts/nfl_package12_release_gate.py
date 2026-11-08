#!/usr/bin/env python3
"""Consolidated release gate: real data, grade schema, and immutable proposal integrity.
Strictly GET-only. Does not create predictions, grades, or injuries.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from nfl_package11_integrated import run
from nfl_package3_live_audit import get_rows

TABLE = 'nfl_prediction_grades'

def evaluate(result, grade_rows):
    plan = result['grade_plan']
    candidates = plan['candidates']
    keys = set()
    for c in candidates:
        key = (str(c['season']),str(c['week']),str(c['game_id']),c['pick_index'])
        if key in keys: raise ValueError('Duplicate proposal')
        keys.add(key)
        if c['grade'] not in ('HIT','MISS','PUSH') or len(c['pick_sha256']) != 64:
            raise ValueError('Invalid grade proposal')
    existing_columns = sorted(set().union(*(set(x) for x in grade_rows))) if grade_rows else []
    # Existing database uses a pick text key, not a verified pick_index/fingerprint
    # mapping. Never guess the storage serialization or update existing rows.
    blockers = ['Grade-table pick serialization and exact insert contract not verified',
                'Backup and restore not yet proven',
                'Touchdown market semantics not verified',
                'Explicit database-write approval not granted']
    if not grade_rows:
        blockers.append('Grade table empty or no sample row; cannot infer column types')
    return {
        'mode':'CONSOLIDATED_RELEASE_GATE_READ_ONLY',
        'season':result['season'],'week':result['week'],
        'snapshot_count':result['snapshot_count'],
        'candidate_count':len(candidates),
        'blocked_reasons':plan['blocked_reasons'],
        'grade_table_sample_count':len(grade_rows),
        'grade_table_observed_columns':existing_columns,
        'candidate_manifest_sha256':hashlib.sha256(json.dumps(candidates,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'grade_writes':0,'prediction_writes':0,'injury_writes':0,
        'activation_allowed':False,'blockers':blockers,
        'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()
    }

def main():
    for flag in ('ENABLE_GRADE_WRITES','ENABLE_PREDICTION_WRITES','ENABLE_INJURY_WRITES'):
        if os.getenv(flag,'').lower() in ('true','yes','1'):
            raise RuntimeError(f'{flag} prohibited')
    from nfl_package10_scheduled_worker import resolve_week
    season,week=resolve_week(os.environ)
    result=run(season,week)
    rows=get_rows(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],TABLE,
                  {'select':'*','season':f'eq.{season}','week':f'eq.{week}','limit':'1'})
    report=evaluate(result,rows)
    dest=Path('package12-output');dest.mkdir(exist_ok=True)
    (dest/'release_gate.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'candidates':report['candidate_count'],'activation_allowed':False,'writes':0}))
if __name__=='__main__':main()
