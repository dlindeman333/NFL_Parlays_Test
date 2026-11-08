#!/usr/bin/env python3
"""Consolidated read-only release gate. Never creates betting picks or writes data."""
import argparse, datetime as dt, hashlib, json, pathlib
from phase3d37l_serializer_dry_run import audit_candidates
from phase3d37j_storage_dry_run import group_candidates, fetch_existing


def evaluate(manifest, candidates, source, existing, now):
    sha = hashlib.sha256(source).hexdigest()
    if sha != manifest.get('source_sha256'):
        raise ValueError('SOURCE_HASH_MISMATCH')
    if len(candidates) != manifest.get('candidate_metrics'):
        raise ValueError('CANDIDATE_COUNT_MISMATCH')
    if len({c.get('logical_key') for c in candidates}) != len(candidates):
        raise ValueError('DUPLICATE_LOGICAL_KEYS')
    if manifest.get('source_freshness_blocker'):
        raise ValueError('STALE_SOURCE')
    acquired = dt.datetime.fromisoformat(manifest['source_acquired_at_utc'].replace('Z','+00:00'))
    if acquired.tzinfo is None or acquired > now or (now-acquired) > dt.timedelta(hours=12):
        raise ValueError('SOURCE_CAPTURE_TOO_OLD')
    accepted, serialized_plans, rejected = audit_candidates(manifest, candidates, now, existing)
    game_plans, storage_rejected = group_candidates(candidates, manifest, now, existing)
    if rejected or storage_rejected or len(accepted) != len(candidates):
        raise ValueError('CANDIDATE_GATE_REJECTED: '+str({'serializer':rejected,'storage':storage_rejected}))
    if {p['game_id'] for p in serialized_plans} != {p['game_id'] for p in game_plans}:
        raise ValueError('GAME_PLAN_MISMATCH')
    return {'mode':'READ_ONLY_CONSOLIDATED_GATE','season':manifest['season'],'week':manifest['week'],
            'evaluated_at_utc':now.isoformat(),'source_sha256':sha,
            'candidate_count':len(accepted),'game_count':len(game_plans),
            'existing_game_skips':sum(p['status']=='SKIP_EXISTING' for p in game_plans),
            'new_game_plans':sum(p['status']=='DRY_RUN_ONLY' for p in game_plans),
            'game_plans':game_plans,'betting_picks_created':0,'snapshots_inserted':0,'grades_inserted':0,
            'database_writes':0,'readiness':'BLOCKED_FOR_WRITES',
            'blockers':['Statistical baselines lack verified sportsbook lines and calibrated probabilities',
                        'App pick reader requires actual market, side, and line for grading',
                        'No automated grading worker is enabled',
                        'A source capture is not proof of upstream per-row publication times',
                        'No restore test or explicit write authorization']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',default='phase3d37h-output');p.add_argument('--output-dir',default='phase3-consolidated-output');a=p.parse_args()
    inp=pathlib.Path(a.input_dir);out=pathlib.Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((inp/'manifest.json').read_text());candidates=json.loads((inp/'candidates.json').read_text());source=(inp/'source.csv').read_bytes()
    now=dt.datetime.now(dt.timezone.utc)
    existing=fetch_existing()
    report=evaluate(manifest,candidates,source,existing,now)
    (out/'consolidated_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('candidate_count','game_count','existing_game_skips','new_game_plans','database_writes','readiness')}))

if __name__=='__main__':main()
