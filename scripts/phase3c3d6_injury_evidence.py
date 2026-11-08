#!/usr/bin/env python3
"""Read-only ESPN injury evidence audit. No database access or writes."""
import csv, json, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BASE=ROOT/'phase3c2_model_baselines.json'
OUT=Path('phase3c3d6-report'); OUT.mkdir(exist_ok=True)
URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'

def norm(x): return re.sub(r'[^a-z0-9]','',str(x or '').lower())
def request(url):
    req=urllib.request.Request(url,headers={'User-Agent':'NFL-Parlay-ReadOnly-Audit/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=50) as f: return json.load(f)
def athlete_id(a):
    return str(a.get('id') or a.get('uid') or '') if isinstance(a,dict) else ''
def extract():
    data=request(URL)
    groups=data.get('injuries')
    if not isinstance(groups,list): raise ValueError('Unexpected injury response: injuries array absent')
    records=[]
    for group in groups:
        if not isinstance(group,dict): continue
        team=group.get('team') or {}
        if not isinstance(team,dict): team={}
        teamcode=team.get('abbreviation') or ''
        for item in group.get('injuries',[]) or []:
            if not isinstance(item,dict):continue
            a=item.get('athlete') or {}
            if not isinstance(a,dict):a={}
            status=item.get('status') or item.get('type') or ''
            if isinstance(status,dict):status=status.get('name') or status.get('description') or status.get('abbreviation') or ''
            records.append({'team':str(teamcode),'player':str(a.get('displayName') or a.get('fullName') or item.get('name') or ''),'espn_id':athlete_id(a),'raw_status':str(status),'source_date':str(item.get('date') or item.get('lastUpdated') or group.get('date') or ''),'raw':item})
    return records

def main():
    baseline=json.loads(BASE.read_text())
    players={}
    for market,pool in baseline['player_pools'].items():
        for team,name,_ in pool:players[(str(team),norm(name))]={'team':str(team),'player':str(name),'markets':set()}
    for market,pool in baseline['player_pools'].items():
        for team,name,_ in pool:players[(str(team),norm(name))]['markets'].add(market)
    rows=[]; error=None; injury=[]
    try: injury=extract()
    except Exception as e:error=f'{type(e).__name__}: {e}'
    aliases={'JAX':'JAC','LAR':'LA','WSH':'WAS'}
    def teamnorm(x):return aliases.get(x.upper(),x.upper())
    for p in players.values():
        matches=[r for r in injury if teamnorm(r['team'])==teamnorm(p['team']) and norm(r['player'])==norm(p['player'])]
        state='UNKNOWN'; raw=''; source_date=''; pid=''; reason='NO_MATCHING_INJURY_EVIDENCE'
        if len(matches)==1:
            m=matches[0];raw=m['raw_status'];source_date=m['source_date'];pid=m['espn_id'];reason='INJURY_REPORT_MATCH_UNVERIFIED_GAME_DAY';state='REPORTED_STATUS_UNVERIFIED'
        elif len(matches)>1:reason='AMBIGUOUS_INJURY_REPORT_MATCH'
        if error:reason='SOURCE_ERROR'
        rows.append({'team':p['team'],'player':p['player'],'markets':','.join(sorted(p['markets'])),'espn_id_from_injury_report':pid,'evidence_status':state,'raw_injury_status':raw,'source_date':source_date,'reason':reason,'game_day_active_verified':False})
    report={'mode':'READ_ONLY_INJURY_EVIDENCE','generated_utc':datetime.now(timezone.utc).isoformat(),'source':URL,'source_error':error,'injury_rows_returned':len(injury),'unique_model_players':len(rows),'injury_evidence_matches':sum(r['evidence_status']!='UNKNOWN' for r in rows),'game_day_active_verified':0,'snapshot_approved':0,'limitations':['Undocumented ESPN API may change without notice','Name+team match is provisional, not stable-ID verification','No final game-day inactive list is checked','No injury report entry does not mean ACTIVE','Report timestamps may be missing or not game-specific','No Supabase access or writes'],'players':rows}
    (OUT/'audit.json').write_text(json.dumps(report,indent=2))
    with (OUT/'players.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['player']);w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in report.items() if k!='players'},indent=2))
    if error:print('WARNING: Injury source unavailable; all players remain UNKNOWN',file=sys.stderr)
    print('READ ONLY: No Supabase writes. No snapshots approved.')

if __name__=='__main__':main()
