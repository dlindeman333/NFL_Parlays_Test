#!/usr/bin/env python3
"""Phase 3D17: read-only historical NFL.com inactive article parser; no eligibility approvals."""
import csv, hashlib, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

URL='https://www.nfl.com/news/week-9-thursday-night-inactives-jacksonville-jaguars-at-baltimore-ravens'
TEAMS={'JAGUARS':'JAX','RAVENS':'BAL'}
POSITIONS={'QB','RB','WR','TE','OT','T','G','C','OL','DL','DE','DT','LB','OLB','ILB','CB','DB','S','FS','SS','K','P','LS','FB','NT'}
OUT=Path('phase3c3d17-report')

def norm(s):
    s=s.lower().replace('’',"'")
    s=re.sub(r'\b(jr|sr|ii|iii|iv)\b','',s)
    return re.sub(r'[^a-z0-9]','',s)

def parse(html):
    soup=BeautifulSoup(html,'html.parser')
    heading=soup.find('h1',string=lambda x: bool(x and 'thursday night inactives' in x.lower()))
    if not heading: return {},['ARTICLE_TITLE_NOT_FOUND']
    # Scan only subsequent headings and their immediately adjacent player-list elements.
    result={}; issues=[]
    for h in heading.find_all_next(['h2','h3','h4']):
        name=h.get_text(' ',strip=True).upper()
        if name not in TEAMS: continue
        if name in result: issues.append('DUPLICATE_TEAM_HEADING_'+name);continue
        players=[]
        for sibling in h.next_siblings:
            if getattr(sibling,'name',None) in ('h2','h3','h4'):break
            if not getattr(sibling,'find_all',None):continue
            nodes=([sibling] if sibling.name=='li' else sibling.find_all('li'))
            for li in nodes:
                value=li.get_text(' ',strip=True)
                m=re.match(r'^([A-Z]{1,4})\s+(.+)$',value)
                if m and m.group(1) in POSITIONS:
                    player=re.sub(r'\s*\([^)]*\)\s*$','',m.group(2)).strip()
                    players.append({'position':m.group(1),'player':player,'raw':value})
        result[TEAMS[name]]=players
    if set(result)!=set(TEAMS.values()):issues.append('BOTH_TEAMS_NOT_FOUND')
    for team,players in result.items():
        if not players:issues.append('EMPTY_TEAM_LIST_'+team)
        if len(players)!=len(set(norm(p['player']) for p in players)):issues.append('DUPLICATE_NAMES_'+team)
    return result,issues

def main():
    OUT.mkdir(exist_ok=True)
    ref=Path(__file__).with_name('phase3c3d12_player_game_evidence.csv')
    with ref.open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    if len(rows)!=41 or len({r['espn_player_id'] for r in rows})!=41: raise ValueError('Reference baseline mismatch; expected 41 unique ESPN IDs')
    req=Request(URL,headers={'User-Agent':'Mozilla/5.0 (compatible; read-only audit)'})
    errors=[];html='';status=None
    try:
        with urlopen(req,timeout=30) as resp:
            status=resp.status;html=resp.read(2_000_000).decode('utf-8','replace')
    except Exception as exc:errors.append('FETCH_FAILED: '+str(exc))
    lists,parse_issues=parse(html) if html else ({},['NO_HTML'])
    errors.extend(parse_issues)
    # Historical test: roster reference games are FUTURE, so never transfer historical inactives to their availability.
    matches=[]
    for r in rows:
        team=r['team']; candidates=[p for p in lists.get(team,[]) if norm(p['player'])==norm(r['player'])]
        matches.append({'player':r['player'],'team':team,'espn_player_id':r['espn_player_id'],
          'reference_game_id':r['game_id'],'reference_kickoff_utc':r['kickoff_utc'],
          'historical_article_name_matches':len(candidates),'historical_article_listed':bool(candidates),
          'current_game_availability':'UNKNOWN','snapshot_approved':False,
          'reason':'HISTORICAL_ARTICLE_NOT_REFERENCE_GAME'})
    audit={'phase':'3C-3D17','retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
      'historical_article_url':URL,'http_status':status,'article_sha256':hashlib.sha256(html.encode()).hexdigest() if html else None,
      'teams_found':list(lists),'historical_inactive_entries':{k:len(v) for k,v in lists.items()},
      'parser_issues':errors,'parser_structure_ok':not errors,'complete_official_report_certified':False,
      'model_players':len(rows),'historical_name_matches':sum(m['historical_article_listed'] for m in matches),
      'reference_game_player_availability_verified':0,'snapshot_approvals':0,'supabase_reads':0,'supabase_writes':0,
      'warning':'Historical source parsing only. Completeness and game-day eligibility are NOT certified.'}
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    with (OUT/'historical_inactives.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['team','position','player','raw']);w.writeheader()
        for team,players in lists.items():
            for p in players:w.writerow({'team':team,**p})
    with (OUT/'player_matches.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(matches[0]));w.writeheader();w.writerows(matches)
    print(json.dumps(audit,indent=2))
    # Network errors should be visible as failed workflow; artifact still uploaded.
    if errors:sys.exit(1)

if __name__=='__main__':main()
