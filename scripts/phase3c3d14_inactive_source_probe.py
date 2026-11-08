#!/usr/bin/env python3
"""Read-only NFL game-day inactive source discovery. No eligibility approvals."""
import csv, json, os, re, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE=Path(__file__).resolve().parent
OUT=Path('phase3c3d14-report'); OUT.mkdir(exist_ok=True)
HEADERS={'User-Agent':'NFLParlayBuilder-ReadOnlySourceAudit/1.0','Accept':'application/json'}
NOW=datetime.now(timezone.utc)

def fetch(url):
    req=urllib.request.Request(url,headers=HEADERS)
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            body=r.read(4_000_000)
            return json.loads(body),None,dict(r.headers)
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
        return None,str(e),{}

def nested_candidates(obj,path='$',depth=0):
    """Discover explicitly labeled inactive-like structures, not arbitrary player mentions."""
    out=[]
    if depth>8:return out
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=path+'.'+str(k)
            if re.search(r'inactiv|scratch|not.?dress',str(k),re.I):
                out.append({'path':p,'value_type':type(v).__name__,'sample':str(v)[:300]})
            if isinstance(v,(dict,list)):out+=nested_candidates(v,p,depth+1)
    elif isinstance(obj,list):
        for i,v in enumerate(obj[:35]):
            if isinstance(v,(dict,list)):out+=nested_candidates(v,path+f'[{i}]',depth+1)
    return out[:120]

rows=list(csv.DictReader((BASE/'phase3c3d12_player_game_evidence.csv').open(encoding='utf-8-sig')))
bygame={}
for p in rows:
    if p.get('game_id'):bygame.setdefault(p['game_id'],[]).append(p)
results=[];players=[]
for game_id,ps in sorted(bygame.items()):
    kickoff=ps[0].get('kickoff_utc','')
    try:dt=datetime.fromisoformat(kickoff.replace('Z','+00:00'))
    except ValueError:dt=None
    until=(dt-NOW).total_seconds()/60 if dt else None
    url=f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}'
    data,error,headers=fetch(url)
    hits=nested_candidates(data) if data else []
    # ESPN summary is NOT an official inactive list; labels alone do not prove validity.
    rec={'game_id':game_id,'kickoff_utc':kickoff,'minutes_until_kickoff':round(until,1) if until is not None else None,
         'inactive_window_started':until is not None and until<=90,
         'source':'ESPN_UNOFFICIAL_GAME_SUMMARY','http_success':data is not None,'error':error,
         'top_level_keys':sorted(data.keys()) if isinstance(data,dict) else [],
         'candidate_inactive_fields':hits,'candidate_count':len(hits),
         'official_inactives_verified':False,'source_checked_at_utc':NOW.isoformat()}
    results.append(rec)
    for p in ps:
        players.append({'team':p['team'],'player':p['player'],'espn_player_id':p['espn_player_id'],
                        'game_id':game_id,'kickoff_utc':kickoff,'inactive_window_started':rec['inactive_window_started'],
                        'espn_summary_retrieved':rec['http_success'],
                        'game_day_inactive_status':'UNKNOWN_NOT_VERIFIED',
                        'injury_status':'NOT_ASSESSED_IN_THIS_PHASE','snapshot_approved':False})
    time.sleep(.15)

summary={'phase':'3C-3D14','generated_at_utc':NOW.isoformat(),'players':len(players),
         'games':len(results),'summary_success':sum(r['http_success'] for r in results),
         'games_with_candidate_fields':sum(bool(r['candidate_count']) for r in results),
         'games_in_90_minute_window':sum(r['inactive_window_started'] for r in results),
         'official_inactives_verified':0,'approved_snapshots':0,'supabase_writes':0,
         'limitations':['ESPN game summary is not an official inactive list.',
          'Candidate fields are schema hints only; no player is certified active or inactive.',
          'A 90-minute window does not guarantee public release of official inactives.',
          'No official NFL.com or team announcement is parsed or verified in this phase.']}
(OUT/'audit.json').write_text(json.dumps(summary,indent=2))
(OUT/'game_source_shapes.json').write_text(json.dumps(results,indent=2))
with (OUT/'player_inactive_evidence.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(players[0]) if players else ['player']);w.writeheader();w.writerows(players)
print(json.dumps(summary,indent=2))
