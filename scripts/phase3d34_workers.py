"""Phase 3D34: deterministic, offline, READ-ONLY automation planning.
No Supabase client, HTTP requests, or write methods are included.
Input JSON must be sourced from verified pregame / postgame pipelines later.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

UTC = dt.timezone.utc

def timestamp(value):
    if not value: return None
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None: raise ValueError('Timezone required')
    return parsed.astimezone(UTC)

def key(row, fields):
    return tuple(row.get(f) for f in fields)

def injury_plan(candidates, existing, now):
    """Returns candidate inserts only; never overwrites existing rows."""
    existing_keys = {key(x, ('season','week','game_id','player_id')) for x in existing}
    inserts, held = [], []
    seen = set()
    for r in candidates:
        k = key(r, ('season','week','game_id','player_id'))
        reason = None
        if any(v is None or v == '' for v in k): reason = 'missing identity'
        elif k in seen or k in existing_keys: reason = 'duplicate or existing'
        elif not r.get('source') or not r.get('designation'): reason = 'missing source or designation'
        else:
            updated = timestamp(r.get('source_updated_at'))
            if updated is None: reason = 'unverified source timestamp'
            elif updated > now: reason = 'future source timestamp'
            elif (now - updated) > dt.timedelta(hours=72): reason = 'stale source'
        seen.add(k)
        (held if reason else inserts).append({'key': list(k), 'reason': reason} if reason else {'key': list(k), 'source':r['source']})
    return {'candidate_inserts': inserts, 'held': held, 'existing_untouched':len(existing)}

def snapshot_plan(games, existing, now):
    existing_keys = {key(x, ('season','week','game_id')) for x in existing}
    ready, held = [], []
    seen=set()
    for g in games:
        k=key(g, ('season','week','game_id'))
        reason=None
        if any(v is None or v == '' for v in k): reason='missing game identity'
        elif k in seen or k in existing_keys: reason='already snapshotted or duplicate'
        elif not g.get('kickoff_verified'): reason='kickoff not independently verified'
        elif not g.get('model_output_verified'): reason='no verified pregame model output'
        elif not isinstance(g.get('picks'), list) or not g['picks']: reason='missing picks'
        elif not g.get('away_team') or not g.get('home_team') or not g.get('model_version'): reason='missing required fields'
        elif not timestamp(g.get('kickoff_at')) or now >= timestamp(g['kickoff_at']): reason='at or after kickoff'
        seen.add(k)
        (held if reason else ready).append({'key':list(k), 'reason':reason} if reason else {'key':list(k),'pick_count':len(g['picks'])})
    return {'eligible_for_future_worker':ready, 'held':held, 'existing_untouched':len(existing)}

def grading_plan(snapshots, final_games, existing_grades):
    """Only identifies gradeable keys; no outcomes calculated without a verified stat mapping."""
    finals={key(g, ('season','week','game_id')):g for g in final_games}
    graded={key(g, ('season','week','game_id','pick_key')) for g in existing_grades}
    ready,held=[],[]
    for snap in snapshots:
        gamekey=key(snap, ('season','week','game_id'))
        final=finals.get(gamekey)
        for p in snap.get('picks',[]):
            pk=p.get('pick_key') if isinstance(p,dict) else None
            grade_key=(*gamekey,pk)
            reason=None
            if not pk: reason='missing stable pick_key'
            elif grade_key in graded: reason='already graded'
            elif not final or final.get('status')!='final' or not final.get('stats_verified'): reason='no verified final statistics'
            elif not p.get('stat_mapping_verified'): reason='no verified pick-to-stat mapping'
            (held if reason else ready).append({'key':list(grade_key),'reason':reason} if reason else {'key':list(grade_key)})
    return {'eligible_for_future_grader':ready,'held':held,'existing_untouched':len(existing_grades)}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True,help='Local fixture JSON; never production credentials')
    parser.add_argument('--output',default='phase3d34_report.json')
    args=parser.parse_args()
    payload=json.loads(Path(args.input).read_text())
    now=timestamp(payload['now'])
    report={'mode':'OFFLINE_DRY_RUN','writes_enabled':False,
            'injuries':injury_plan(payload.get('injury_candidates',[]),payload.get('existing_injuries',[]),now),
            'snapshots':snapshot_plan(payload.get('games',[]),payload.get('existing_snapshots',[]),now),
            'grades':grading_plan(payload.get('existing_snapshots',[]),payload.get('final_games',[]),payload.get('existing_grades',[]))}
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'mode':report['mode'],'injury_candidates':len(report['injuries']['candidate_inserts']), 'snapshot_candidates':len(report['snapshots']['eligible_for_future_worker']), 'grade_candidates':len(report['grades']['eligible_for_future_grader'])}))

if __name__=='__main__': main()
