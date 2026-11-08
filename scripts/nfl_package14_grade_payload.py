#!/usr/bin/env python3
"""Map verified-schema grading proposals to non-writing, fail-closed payload previews."""
import hashlib
import json
from datetime import datetime, timezone

COLUMNS = ('season','week','game_id','pick_key','outcome','actual_value','grading_note','stats_source','graded_at')
OUTCOMES = {'HIT':'hit','MISS':'miss','PUSH':'push'}

def stage(plan, *, key_resolver=None, existing_keys=()):
    """No key resolver is provided by default: don't invent the app's pick_key serialization."""
    output=[]; blocked=[]; seen=set(); existing=set(existing_keys)
    for item in plan.get('candidates',[]):
        identity=(item['season'],item['week'],str(item['game_id']),item['pick_index'])
        if identity in seen: raise ValueError('Duplicate proposal identity')
        seen.add(identity)
        if item.get('grade') not in OUTCOMES: raise ValueError('Unexpected outcome')
        if not isinstance(item.get('pick_sha256'),str) or len(item['pick_sha256'])!=64: raise ValueError('Invalid fingerprint')
        key=key_resolver(item) if key_resolver else None
        if not isinstance(key,str) or not key.strip():
            blocked.append({'identity':list(identity),'reason':'PICK_KEY_CONTRACT_NOT_VERIFIED'});continue
        dbkey=(item['season'],item['week'],str(item['game_id']),key)
        if dbkey in existing: blocked.append({'identity':list(identity),'reason':'EXISTING_GRADE_PRESERVED'});continue
        evidence=item.get('evidence') or {}
        # Actual values must come from verified individual-game evidence, not from projection baselines.
        actual=evidence.get('actual_value')
        if actual is not None and (type(actual) not in (int,float) or not (-1e9 < actual < 1e9)):
            blocked.append({'identity':list(identity),'reason':'INVALID_ACTUAL_VALUE'});continue
        payload={'season':item['season'],'week':item['week'],'game_id':str(item['game_id']),
                 'pick_key':key,'outcome':OUTCOMES[item['grade']], 'actual_value':actual,
                 'grading_note':'Proposed from verified final-game evidence; review before activation',
                 'stats_source':'espn_game_boxscore' if actual is not None else 'espn_final_score',
                 'graded_at':datetime.now(timezone.utc).isoformat()}
        output.append(payload)
    manifest=hashlib.sha256(json.dumps(output,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'mode':'SCHEMA_MAPPED_PREVIEW_ONLY','writes':0,'activation_allowed':False,
            'schema_columns':list(COLUMNS),'staged_count':len(output),'blocked':blocked,
            'payload_manifest_sha256':manifest,'payloads':output,
            'blockers':['Verify app pick_key serialization and grade outcome values',
                        'Prove isolated restore of the private backup',
                        'Resolve touchdown market contract and verify per-game stats',
                        'Obtain explicit write authorization']}
