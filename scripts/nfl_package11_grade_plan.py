#!/usr/bin/env python3
"""Build deterministic, fail-closed grade proposals. No network mutations."""
import hashlib
import json
from collections import Counter

ELIGIBLE = {'HIT', 'MISS', 'PUSH'}

def canonical_pick(pick):
    if not isinstance(pick, dict):
        raise ValueError('Invalid pick')
    return json.dumps(pick, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def build_plan(snapshots, report, season, week):
    by_game = {}
    for snap in snapshots:
        gid = str(snap.get('game_id') or '')
        if not gid or gid in by_game or str(snap.get('season')) != str(season) or str(snap.get('week')) != str(week):
            raise ValueError('Duplicate/invalid/mismatched snapshot')
        if not isinstance(snap.get('picks'), list):
            raise ValueError('Invalid picks array')
        by_game[gid] = snap
    candidates = []
    blocked = Counter()
    seen = set()
    for result in report.get('results', []):
        gid = str(result.get('game_id') or '')
        index = result.get('pick_index')
        if gid not in by_game or type(index) is not int or not 0 <= index < len(by_game[gid]['picks']):
            raise ValueError('Grading result not bound to a saved pick')
        identity = (gid, index)
        if identity in seen:
            raise ValueError('Duplicate grade result')
        seen.add(identity)
        pick = by_game[gid]['picks'][index]
        status = result.get('status')
        if status not in ELIGIBLE:
            blocked[str(result.get('reason') or 'Unavailable')] += 1
            continue
        if pick.get('market') == 'player' and pick.get('stat') == 'touchdowns':
            blocked['Unverified touchdown contract'] += 1
            continue
        fingerprint = hashlib.sha256(canonical_pick(pick).encode()).hexdigest()
        candidates.append({'season': season, 'week': week, 'game_id': gid,
                           'pick_index': index, 'pick_sha256': fingerprint,
                           'grade': status, 'evidence': {k:v for k,v in result.items() if k not in ('game_id','pick_index','status')}})
    return {'mode': 'GRADE_PROPOSAL_ONLY', 'write_enabled': False,
            'database_writes': 0, 'candidates': candidates,
            'candidate_count': len(candidates), 'blocked_reasons': dict(blocked),
            'grade_table_write_contract': 'UNVERIFIED',
            'readiness': 'BLOCKED_PENDING_SCHEMA_BACKUP_AND_EXPLICIT_WRITE_APPROVAL'}
