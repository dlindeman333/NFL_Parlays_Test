#!/usr/bin/env python3
"""Package 14: read-only end-to-end grading and verified-schema staging."""
import json, os
from pathlib import Path
from nfl_package10_scheduled_worker import resolve_week
from nfl_package11_integrated import run
from nfl_package14_grade_payload import stage

def main():
    for flag in ('ENABLE_GRADE_WRITES','ENABLE_PREDICTION_WRITES','ENABLE_INJURY_WRITES'):
        if os.getenv(flag,'').lower() in ('true','yes','1'): raise RuntimeError(f'{flag} forbidden')
    season,week=resolve_week(os.environ)
    result=run(season,week)
    staged=stage(result['grade_plan'])
    # No guessed pick keys: no write-ready records until app contract is confirmed.
    out={'season':season,'week':week,'snapshots':result['snapshot_count'],
         'grade_candidates':result['grade_plan']['candidate_count'],
         'schema_staging':staged,'database_writes':0}
    path=Path('package14-output');path.mkdir(exist_ok=True)
    (path/'grade_schema_staging.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'candidates':out['grade_candidates'],'staged':staged['staged_count'],'writes':0}))
if __name__=='__main__':main()
