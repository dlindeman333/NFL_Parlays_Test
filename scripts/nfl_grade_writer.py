"""Fail-closed, create-only grade writer. Never called by included GitHub workflow."""
import json, os, urllib.request, urllib.error
from nfl_grade_contract import validate_row

def prepare_rows(plan, snapshots, existing_keys=()):
    """Resolve picks from original immutable snapshot and create stable keys."""
    from nfl_grade_contract import pick_key
    from nfl_package14_grade_payload import stage
    by_game={(int(s['season']),int(s['week']),str(s['game_id'])):s for s in snapshots}
    def resolver(item):
        snap=by_game.get((int(item['season']),int(item['week']),str(item['game_id'])))
        if not snap: return None
        idx=item['pick_index']
        if type(idx) is not int or idx<0 or idx>=len(snap['picks']): return None
        from nfl_package11_grade_plan import canonical_pick
        import hashlib
        pick=snap['picks'][idx]
        if hashlib.sha256(canonical_pick(pick).encode()).hexdigest()!=item['pick_sha256']:
            raise ValueError('Snapshot pick changed after proposal; abort')
        return pick_key(pick,idx)
    result=stage(plan,key_resolver=resolver,existing_keys=existing_keys)
    for row in result['payloads']: validate_row(row)
    result['mode']='VERSIONED_CONTRACT_PREVIEW_ONLY'
    result['activation_allowed']=False
    return result

def write_once(rows, *, backup_restore_verified=False, approval=False):
    """Deliberately unavailable until an isolated restore and explicit launch approval.

    This release contains no production mutation path. A separate reviewed release
    must implement a conditional create-only insert, conflict handling, and audit log.
    """
    raise PermissionError('Grade writes disabled: isolated restore and explicit approval required')
