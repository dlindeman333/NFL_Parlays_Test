#!/usr/bin/env python3
"""Read-only automation gating tests. No API mutations, no database writes."""
import json,datetime as dt,pathlib,collections
OUT=pathlib.Path('phase3d27-29-report');OUT.mkdir(exist_ok=True)
UTC=dt.timezone.utc

def pregame_gate(now,kickoff,existing_snapshot,official_inactives_verified,source_fresh,game_verified,history_ok):
    if existing_snapshot:return 'BLOCK_EXISTING_SNAPSHOT'
    if not game_verified:return 'BLOCK_UNVERIFIED_GAME'
    if not history_ok:return 'HOLD_INSUFFICIENT_HISTORY'
    if not source_fresh:return 'HOLD_STALE_INJURY_EVIDENCE'
    if not official_inactives_verified:return 'HOLD_OFFICIAL_INACTIVES_UNKNOWN'
    if kickoff<=now:return 'BLOCK_KICKOFF_ALREADY_PASSED'
    return 'PREVIEW_ELIGIBLE_NOT_AUTHORIZED'

def grading_gate(game_final,snapshot_exists,already_graded,stat_verified):
    if not snapshot_exists:return 'BLOCK_NO_AUTHENTIC_PREGAME_SNAPSHOT'
    if already_graded:return 'NO_CHANGE_ALREADY_GRADED'
    if not game_final:return 'HOLD_GAME_NOT_FINAL'
    if not stat_verified:return 'HOLD_UNVERIFIED_RESULTS'
    return 'PREVIEW_ELIGIBLE_NOT_AUTHORIZED'

def injury_gate(source_updated,stored_updated,source_valid,game_verified):
    if not source_valid or not game_verified:return 'HOLD_SOURCE_OR_GAME_UNVERIFIED'
    if source_updated is None:return 'HOLD_SOURCE_TIMESTAMP_MISSING'
    if stored_updated is not None and source_updated<=stored_updated:return 'BLOCK_OLDER_OR_EQUAL_TIMESTAMP'
    return 'PREVIEW_ELIGIBLE_NOT_AUTHORIZED'

def main():
    now=dt.datetime(2026,11,8,12,tzinfo=UTC); future=now+dt.timedelta(hours=3)
    checks={
      'existing_snapshot_protected':pregame_gate(now,future,True,True,True,True,True)=='BLOCK_EXISTING_SNAPSHOT',
      'unknown_inactives_held':pregame_gate(now,future,False,False,True,True,True)=='HOLD_OFFICIAL_INACTIVES_UNKNOWN',
      'kickoff_passed_blocked':pregame_gate(now,now,False,True,True,True,True)=='BLOCK_KICKOFF_ALREADY_PASSED',
      'stale_injury_held':pregame_gate(now,future,False,True,False,True,True)=='HOLD_STALE_INJURY_EVIDENCE',
      'game_unverified_blocked':pregame_gate(now,future,False,True,True,False,True)=='BLOCK_UNVERIFIED_GAME',
      'history_short_held':pregame_gate(now,future,False,True,True,True,False)=='HOLD_INSUFFICIENT_HISTORY',
      'no_snapshot_cannot_grade':grading_gate(True,False,False,True)=='BLOCK_NO_AUTHENTIC_PREGAME_SNAPSHOT',
      'duplicate_grading_idempotent':grading_gate(True,True,True,True)=='NO_CHANGE_ALREADY_GRADED',
      'unfinished_game_held':grading_gate(False,True,False,True)=='HOLD_GAME_NOT_FINAL',
      'unverified_stat_held':grading_gate(True,True,False,False)=='HOLD_UNVERIFIED_RESULTS',
      'older_injury_blocked':injury_gate(now,now+dt.timedelta(hours=1),True,True)=='BLOCK_OLDER_OR_EQUAL_TIMESTAMP',
      'equal_injury_blocked':injury_gate(now,now,True,True)=='BLOCK_OLDER_OR_EQUAL_TIMESTAMP',
      'missing_timestamp_held':injury_gate(None,None,True,True)=='HOLD_SOURCE_TIMESTAMP_MISSING',
      'unverified_game_injury_held':injury_gate(now,None,True,False)=='HOLD_SOURCE_OR_GAME_UNVERIFIED',
      'safe_case_still_not_authorized':pregame_gate(now,future,False,True,True,True,True)=='PREVIEW_ELIGIBLE_NOT_AUTHORIZED',
    }
    previous={}
    for name in ('phase3c3d22','phase3c3d23','phase3c3d24','phase3c3d25'):
      path=pathlib.Path(name+'-report/audit.json')
      previous[name]=json.loads(path.read_text()) if path.exists() else {'error':'missing audit'}
    pass_count=sum(checks.values())
    report={'phase':'3D27-29 DEVELOPMENT PREVIEW','checks_passed':pass_count,'checks_total':len(checks),'checks':checks,
     'source_audits':previous,'writes_enabled':False,'injury_sync_scheduled':False,'prediction_snapshot_scheduled':False,'grading_scheduled':False,
     'production_ready':False,'backup_verified':False,'restore_tested':False,
     'notes':['No write-capable workflows are installed by this package.','Rules are unit tested, not connected to a real grading pipeline.',
       'Prior authentic snapshots are never backfilled.','ESPN injury reports are not official game-day inactive confirmation.',
       'A separate scoped application-data export and isolated restore test is required before any production write.']}
    (OUT/'automation_readiness.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'checks_passed':pass_count,'checks_total':len(checks),'writes_enabled':False,'source_audits':{k:v.get('status',v.get('phase')) for k,v in previous.items()}},indent=2))
    if pass_count!=len(checks) or any('error' in x for x in previous.values()):raise SystemExit('Readiness failed closed')
if __name__=='__main__':main()
