#!/usr/bin/env python3
"""Read-only NFL matchup/identity evidence audit. No database access or writes."""
import csv, datetime as dt, json, pathlib, urllib.request
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path('phase3c3d12-report'); OUT.mkdir(exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date}&limit=1000'
TEAM_MAP = {'JAX':'JAC','WSH':'WAS','LAR':'LA','KAN':'KC','GNB':'GB','NWE':'NE','NOR':'NO','SFO':'SF','TAM':'TB','LVR':'LV'}

def fetch(url):
    req=urllib.request.Request(url, headers={'User-Agent':'NFL-Parlay-ReadOnly-Audit/3D12','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)

def parse_date(s):
    try: return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(dt.timezone.utc)
    except (ValueError,AttributeError): return None

def main():
    base=json.loads((ROOT/'phase3c2_model_baselines.json').read_text())
    mapping=json.loads((ROOT/'phase3c3d8_player_ids.json').read_text())
    expected={(team,name) for pool in base['player_pools'].values() for team,name,*_ in pool}
    lookup={(x['team'],x['player']):str(x['espn_id']) for x in mapping}
    # Proposed identity from the user's earlier read-only roster audit. Never overwrite original.
    proposed=dict(lookup); proposed[('JAC','Trevor Lawrence')]='4360310'
    proposal=[{'team':t,'player':p,'espn_id':proposed.get((t,p),''),'source':'3D11_UNIQUE_ROSTER_CANDIDATE_REQUIRES_REVIEW' if (t,p)==('JAC','Trevor Lawrence') else '3D8_MAPPING','approved_for_write':False} for t,p in sorted(expected)]
    with (OUT/'proposed_player_ids.json').open('w') as f: json.dump(proposal,f,indent=2)
    games={}; errors=[]; days=14
    # Calendar-day queries; deduplicate ESPN game IDs, and do not invent kickoff times.
    for i in range(days+1):
        date=(NOW+dt.timedelta(days=i)).strftime('%Y%m%d')
        try:
            data=fetch(URL.format(date=date))
            for e in data.get('events',[]):
                eid=str(e.get('id',''))
                comps=(e.get('competitions') or [{}])[0].get('competitors',[])
                teams=[TEAM_MAP.get(str(c.get('team',{}).get('abbreviation','')).upper(),str(c.get('team',{}).get('abbreviation','')).upper()) for c in comps]
                kickoff=parse_date(e.get('date'))
                if eid and len(teams)==2 and kickoff and NOW <= kickoff <= NOW+dt.timedelta(days=14):
                    games[eid]={'game_id':eid,'teams':teams,'kickoff_utc':kickoff.isoformat(),'status':e.get('status',{}).get('type',{}).get('name','UNKNOWN')}
        except Exception as exc: errors.append({'date':date,'error':str(exc)[:250]})
    rows=[]
    for t,p in sorted(expected):
        candidates=sorted([g for g in games.values() if t in g['teams']],key=lambda g:g['kickoff_utc'])
        game=candidates[0] if candidates else None
        opponent=next((x for x in game['teams'] if x!=t),'') if game else ''
        rows.append({'team':t,'player':p,'espn_player_id':proposed.get((t,p),''),'mapping_source':'PROPOSED_REVIEW' if (t,p)==('JAC','Trevor Lawrence') else 'EXISTING','game_id':game['game_id'] if game else '', 'opponent':opponent,'kickoff_utc':game['kickoff_utc'] if game else '', 'matchup_evidence':'ESPN_SCOREBOARD' if game else 'NO_UPCOMING_GAME_FOUND','game_specific_injury_report':'NOT_RETRIEVED','injury_report_timestamp':'','official_inactive_list':'NOT_RETRIEVED','availability':'UNVERIFIED','snapshot_approved':False})
    with (OUT/'player_game_evidence.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'mode':'READ_ONLY_GAME_SPECIFIC_EVIDENCE_FRAMEWORK','generated_utc':NOW.isoformat(),'baseline_players':len(expected),'original_mappings':len(lookup),'proposed_mappings':len(proposed),'trevor_lawrence_proposed_id':'4360310','proposed_identity_requires_review':True,'scoreboard_days_requested':days+1,'unique_upcoming_games':len(games),'players_with_upcoming_matchup':sum(bool(r['game_id']) for r in rows),'players_without_upcoming_matchup':sum(not r['game_id'] for r in rows),'scoreboard_request_errors':errors,'game_specific_injury_reports_verified':0,'official_game_day_inactives_verified':0,'snapshot_approved':0,'database_writes':0,'limitations':['ESPN scoreboard is unofficial and may change','Matchup association does not verify injury status','Proposed Trevor Lawrence ID is not applied to existing mapping','No injury reports or official inactive lists retrieved','No automatic approval or database synchronization']}
    (OUT/'audit.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    if errors and not games: raise SystemExit('All scoreboard probes failed or returned no upcoming games; inspect report')
if __name__=='__main__': main()
