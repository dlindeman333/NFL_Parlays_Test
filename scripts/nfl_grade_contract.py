"""Versioned cloud-grade contract; additive to existing app, not an inferred legacy key."""
import hashlib, json, re

VALID_OUTCOMES={'hit','miss','push'}

def canonical_pick(pick):
    if not isinstance(pick,dict): raise ValueError('Pick must be an object')
    return json.dumps(pick,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def pick_key(pick, index):
    if type(index) is not int or index < 0: raise ValueError('Invalid pick index')
    digest=hashlib.sha256(canonical_pick(pick).encode('utf-8')).hexdigest()
    return f'v1:{index}:{digest}'

def validate_row(row):
    required={'season','week','game_id','pick_key','outcome'}
    if not required <= row.keys(): raise ValueError('Missing grade fields')
    if type(row['season']) is not int or type(row['week']) is not int or not 1<=row['week']<=22: raise ValueError('Invalid season/week')
    if not str(row['game_id']).isdigit(): raise ValueError('Invalid game ID')
    if not re.fullmatch(r'v1:\d+:[0-9a-f]{64}',str(row['pick_key'])): raise ValueError('Invalid versioned pick key')
    if row['outcome'] not in VALID_OUTCOMES: raise ValueError('Invalid outcome')
    if row.get('actual_value') is not None and (type(row['actual_value']) not in (int,float) or not -1e9<row['actual_value']<1e9): raise ValueError('Invalid actual value')
    return True
