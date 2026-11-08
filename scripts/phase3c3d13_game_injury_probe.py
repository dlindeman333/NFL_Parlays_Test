#!/usr/bin/env python3
"""Read-only ESPN game-summary injury/inactive source discovery. No Supabase access.

Do not infer a player's clearance from absence in the feed or ESPN roster 'Active'.
"""
import csv, datetime as dt, hashlib, json, pathlib, re, time, urllib.request
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path('phase3c3d13-report')
OUT.mkdir(exist_ok=True)
SOURCE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={}'
NOW = dt.datetime.now(dt.timezone.utc)

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'NFL-Parlay-ReadOnly-Audit/3D13','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as resp:
        raw=resp.read(8_000_000)
    return json.loads(raw),hashlib.sha256(raw).hexdigest()

def norm(x): return re.sub(r'[^a-z0-9]','',str(x).lower())

def parse_date(s):
    try: return dt.datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(dt.timezone.utc)
    except (ValueError,TypeError): return None

def summarize_structure(data):
    """Record only structure and counts, not arbitrary payloads or personal data."""
    found=[]
    def walk(obj,path='',depth=0):
        if depth>7 or len(found)>250: return
        if isinstance(obj,dict):
            for key,val in obj.items():
                here=f'{path}.{key}' if path else key
                if any(term in key.lower() for term in ('injur','inactive','practice')):
                    found.append({'path':here,'type':type(val).__name__,'size':len(val) if isinstance(val,(list,dict)) else None})
                if isinstance(val,(list,dict)): walk(val,here,depth+1)
        elif isinstance(obj,list):
            for val in obj[:3]: walk(val,path+'[]',depth+1)
    walk(data)
    return found

def extract_explicit_game_evidence(data):
    """Conservative: only explicitly named injury/inactive containers; do not treat player stats as evidence."""
    evidence=[]
    def walk(obj,path='',depth=0):
        if depth>8 or len(evidence)>2000: return
        if isinstance(obj,dict):
            for key,val in obj.items():
                here=f'{path}.{key}' if path else key
                if key.lower() in ('injuries','inactives','inactiveplayers') and isinstance(val,list):
                    kind='INACTIVE_LIST' if 'inactive' in key.lower() else 'INJURY_LIST'
                    for entry in val:
                        if not isinstance(entry,dict): continue
                        athlete=entry.get('athlete') if isinstance(entry.get('athlete'),dict) else {}
                        # Some summaries wrap an athlete in a nested player object.
                        player=entry.get('player') if isinstance(entry.get('player'),dict) else {}
                        athlete=athlete or player
                        ident=athlete.get('id') or entry.get('athleteId') or entry.get('playerId')
                        name=athlete.get('displayName') or athlete.get('fullName') or entry.get('displayName')
                        status=entry.get('status') or entry.get('type') or entry.get('designation')
                        if isinstance(status,dict): status=status.get('displayName') or status.get('name') or status.get('type')
                        stamp=entry.get('date') or entry.get('updated') or entry.get('lastUpdated')
                        evidence.append({'kind':kind,'path':here,'player_id':str(ident or ''),'player_name':str(name or ''),'status':str(status or ''),'reported_at':str(stamp or '')})
                if isinstance(val,(dict,list)): walk(val,here,depth+1)
        elif isinstance(obj,list):
            for val in obj[:1000]: walk(val,path+'[]',depth+1)
    walk(data)
    return evidence

def run():
    with (ROOT/'phase3c3d12_player_game_evidence.csv').open(newline='') as f: players=list(csv.DictReader(f))
    game_ids=sorted({r['game_id'] for r in players if r['game_id']})
    results={}; errors=[]; raw_evidence=[]
    for idx,gid in enumerate(game_ids):
        try:
            data,digest=get(SOURCE.format(gid))
            structures=summarize_structure(data)
            entries=extract_explicit_game_evidence(data)
            results[gid]={'request_ok':True,'sha256':digest,'top_level_keys':sorted(data) if isinstance(data,dict) else [],'candidate_paths':structures,'injury_entries_found':sum(e['kind']=='INJURY_LIST' for e in entries),'inactive_entries_found':sum(e['kind']=='INACTIVE_LIST' for e in entries)}
            raw_evidence.extend([dict(e,game_id=gid) for e in entries])
        except Exception as exc:
            errors.append({'game_id':gid,'error':str(exc)[:250]})
            results[gid]={'request_ok':False,'candidate_paths':[],'injury_entries_found':0,'inactive_entries_found':0}
        if idx<len(game_ids)-1: time.sleep(0.12)
    rows=[]
    for p in players:
        gid=p['game_id']; pid=p['espn_player_id']; name=p['player']
        matches=[e for e in raw_evidence if e['game_id']==gid and ((e['player_id'] and e['player_id']==pid) or (not e['player_id'] and norm(e['player_name'])==norm(name)))]
        injury=[e for e in matches if e['kind']=='INJURY_LIST']
        inactive=[e for e in matches if e['kind']=='INACTIVE_LIST']
        statuses=sorted({e['status'] for e in matches if e['status']})
        # Discovery only: game-summary data is not verified as official NFL reports.
        rows.append({'team':p['team'],'player':name,'espn_player_id':pid,'game_id':gid,'opponent':p['opponent'],'kickoff_utc':p['kickoff_utc'],'game_summary_retrieved':results.get(gid,{}).get('request_ok',False),'injury_entries_matched':len(injury),'inactive_entries_matched':len(inactive),'source_statuses':' | '.join(statuses),'source_timestamps':' | '.join(sorted({e['reported_at'] for e in matches if e['reported_at']})),'evidence_class':'UNVERIFIED_GAME_SUMMARY_ENTRY' if matches else 'NO_GAME_SPECIFIC_EVIDENCE','official_inactives_verified':False,'snapshot_approved':False})
    with (OUT/'player_game_evidence.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (OUT/'game_source_shapes.json').write_text(json.dumps(results,indent=2))
    # Omit arbitrary raw ESPN response; store only minimal extracted candidate fields.
    with (OUT/'source_entries.csv').open('w',newline='') as f:
        fields=['game_id','kind','path','player_id','player_name','status','reported_at'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(raw_evidence)
    audit={'mode':'READ_ONLY_GAME_SUMMARY_INJURY_DISCOVERY','generated_utc':NOW.isoformat(),'baseline_players':len(players),'unique_games_requested':len(game_ids),'successful_game_requests':sum(x['request_ok'] for x in results.values()),'failed_game_requests':len(errors),'source_injury_entries':sum(x['injury_entries_found'] for x in results.values()),'source_inactive_entries':sum(x['inactive_entries_found'] for x in results.values()),'players_with_game_linked_entries':sum(x['evidence_class']=='UNVERIFIED_GAME_SUMMARY_ENTRY' for x in rows),'official_game_inactives_verified':0,'snapshot_approved':0,'database_writes':0,'errors':errors,'limitations':['ESPN summary endpoint is unofficial and undocumented','This is a structural source probe, not a verified official injury report','No evidence does not imply active/healthy','Reported game-linked entries are not certified as current or complete','Trevor Lawrence mapping remains a proposal','No Supabase access or writes']}
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))
    if len(players)!=41: raise SystemExit('Expected 41 player rows; inspect inputs and report')
    if not any(x['request_ok'] for x in results.values()): raise SystemExit('All ESPN game summary requests failed; inspect artifact')

if __name__=='__main__': run()
