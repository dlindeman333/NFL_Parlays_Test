#!/usr/bin/env python3
"""Phase 3C-3D18: deterministic, offline, read-only eligibility rule tests.
No live source retrieval; simulated fixtures MUST NOT be used for snapshot approval.
"""
import csv, json, os
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
REFERENCE=Path(__file__).with_name('phase3c3d12_player_game_evidence.csv')
OUT=ROOT/'phase3c3d18-report'
ALLOWED={'ACTIVE','QUESTIONABLE','DOUBTFUL','OUT','INJURED_RESERVE','UNKNOWN'}

def decide(player, evidence, now):
    reasons=[]
    if evidence.get('game_id') != player['game_id'] or evidence.get('team') != player['team']:
        reasons.append('GAME_OR_TEAM_MISMATCH')
    if evidence.get('player_id') != player['espn_player_id']:
        reasons.append('PLAYER_ID_MISMATCH')
    if evidence.get('source_type') != 'OFFICIAL_GAME_REPORT':
        reasons.append('UNVERIFIED_SOURCE')
    if not evidence.get('both_team_lists_complete'):
        reasons.append('INACTIVE_LIST_INCOMPLETE')
    if evidence.get('ambiguous_player_match'):
        reasons.append('AMBIGUOUS_PLAYER_MATCH')
    kickoff=datetime.fromisoformat(player['kickoff_utc'].replace('Z','+00:00'))
    issued=evidence.get('report_published_at')
    try:
        published=datetime.fromisoformat(issued.replace('Z','+00:00')) if issued else None
    except (ValueError,AttributeError):
        published=None
    if not published or published.tzinfo is None or published > now or published > kickoff:
        reasons.append('INVALID_OR_MISSING_REPORT_TIMESTAMP')
    elif published < kickoff-timedelta(hours=4):
        reasons.append('REPORT_TOO_EARLY_FOR_INACTIVES')
    if now >= kickoff:
        reasons.append('KICKOFF_NOT_IN_FUTURE')
    if reasons:
        return 'UNKNOWN', sorted(set(reasons)), False
    inactive=evidence.get('inactive_player_ids',[])
    if player['espn_player_id'] in inactive:
        return 'CONFIRMED_INACTIVE', ['ON_COMPLETE_OFFICIAL_INACTIVE_LIST'], False
    if evidence.get('emergency_qb_player_ids') and player['espn_player_id'] in evidence['emergency_qb_player_ids']:
        return 'SPECIAL_EMERGENCY_QB', ['EMERGENCY_THIRD_QB_RULE_REVIEW'], False
    status=evidence.get('injury_status','UNKNOWN').upper()
    if status not in ALLOWED: status='UNKNOWN'
    if status in ('OUT','INJURED_RESERVE'):
        return 'BLOCK', ['INJURY_'+status], False
    if status in ('QUESTIONABLE','DOUBTFUL'):
        return 'HOLD', ['INJURY_'+status], False
    if status == 'UNKNOWN':
        return 'UNKNOWN', ['NO_GAME_SPECIFIC_INJURY_CLEARANCE'], False
    # Not on a complete inactive list is not a guarantee of participation.
    return 'NOT_LISTED', ['ABSENT_FROM_COMPLETE_LIST_NOT_ACTIVE_PROOF'], False

def main():
    with REFERENCE.open(newline='',encoding='utf-8-sig') as f: players=list(csv.DictReader(f))
    assert len(players)==41, f'Expected 41 player reference rows, got {len(players)}'
    assert len({(p['team'],p['espn_player_id']) for p in players})==41
    p=next(p for p in players if p['team']=='JAC')
    # Use a controlled simulated pregame clock; no historical results are used to approve real predictions.
    kickoff=datetime.fromisoformat(p['kickoff_utc'])
    now=kickoff-timedelta(minutes=20)
    base={'game_id':p['game_id'],'team':p['team'],'player_id':p['espn_player_id'],
          'source_type':'OFFICIAL_GAME_REPORT','both_team_lists_complete':True,
          'report_published_at':(kickoff-timedelta(minutes=70)).isoformat(),
          'inactive_player_ids':[],'injury_status':'ACTIVE'}
    cases={
        'complete_not_listed':({},'NOT_LISTED'),
        'explicit_inactive':({'inactive_player_ids':[p['espn_player_id']]},'CONFIRMED_INACTIVE'),
        'questionable':({'injury_status':'QUESTIONABLE'},'HOLD'),
        'doubtful':({'injury_status':'DOUBTFUL'},'HOLD'),
        'out':({'injury_status':'OUT'},'BLOCK'),
        'injured_reserve':({'injury_status':'INJURED_RESERVE'},'BLOCK'),
        'no_injury_evidence':({'injury_status':'UNKNOWN'},'UNKNOWN'),
        'incomplete_lists':({'both_team_lists_complete':False},'UNKNOWN'),
        'wrong_game':({'game_id':'wrong-game'},'UNKNOWN'),
        'wrong_team':({'team':'WRONG'},'UNKNOWN'),
        'wrong_player':({'player_id':'999'},'UNKNOWN'),
        'unverified_source':({'source_type':'ESPN_GENERAL_FEED'},'UNKNOWN'),
        'ambiguous_name':({'ambiguous_player_match':True},'UNKNOWN'),
        'missing_timestamp':({'report_published_at':None},'UNKNOWN'),
        'too_early':({'report_published_at':(kickoff-timedelta(hours=6)).isoformat()},'UNKNOWN'),
        'future_report':({'report_published_at':(now+timedelta(minutes=1)).isoformat()},'UNKNOWN'),
        'emergency_qb':({'emergency_qb_player_ids':[p['espn_player_id']]},'SPECIAL_EMERGENCY_QB'),
    }
    results=[]
    for name,(override,expected) in cases.items():
        evidence={**base,**override}
        decision,reasons,approved=decide(p,evidence,now)
        results.append({'case':name,'expected':expected,'actual':decision,'passed':decision==expected and not approved,'reasons':reasons,'snapshot_approved':approved})
    # Apply no evidence to each real reference row. This is a missing-data audit, not an availability check.
    baseline=[]
    for player in players:
        baseline.append({'team':player['team'],'player':player['player'],'espn_player_id':player['espn_player_id'],
                         'game_id':player['game_id'],'decision':'UNKNOWN','reason':'NO_LIVE_GAME_SPECIFIC_EVIDENCE',
                         'snapshot_approved':False})
    OUT.mkdir(exist_ok=True)
    with (OUT/'test_cases.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['case','expected','actual','passed','reasons','snapshot_approved']);w.writeheader()
        for row in results:w.writerow({**row,'reasons':';'.join(row['reasons'])})
    with (OUT/'player_decisions.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(baseline[0]));w.writeheader();w.writerows(baseline)
    report={'phase':'3C-3D18','mode':'OFFLINE_SIMULATED_RULE_TESTS_READ_ONLY',
            'reference_players':len(players),'test_cases':len(results),'tests_passed':sum(x['passed'] for x in results),
            'tests_failed':[x['case'] for x in results if not x['passed']],
            'live_inactive_reports_retrieved':0,'real_player_statuses_verified':0,'snapshot_approvals':0,
            'supabase_reads':0,'supabase_writes':0,
            'warning':'Simulated fixtures validate rules only. No actual player availability or official list completeness is certified.'}
    (OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    if report['tests_failed']:raise SystemExit(1)

if __name__=='__main__':main()
