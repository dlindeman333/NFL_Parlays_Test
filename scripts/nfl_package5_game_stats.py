#!/usr/bin/env python3
"""Per-game ESPN boxscore evidence; deliberately read-only and fail-closed."""
import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from nfl_package3_live_audit import get_rows
from nfl_package4_final_evidence import fetch_scoreboard, normalize_games

SUMMARY='https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary'
TEAM_ALIASES={'WSH':'WAS','WFT':'WAS','JAC':'JAX','LA':'LAR','STL':'LAR','SD':'LAC','OAK':'LV'}
def team(t):
    t=str(t or '').strip().upper()
    return TEAM_ALIASES.get(t,t)

def fetch_summary(game_id, opener=urllib.request.urlopen):
    if not re.fullmatch(r'\d{7,12}',str(game_id)): raise ValueError('Invalid ESPN game ID')
    req=urllib.request.Request(SUMMARY+'?'+urllib.parse.urlencode({'event':str(game_id)}),headers={'User-Agent':'NFL-Parlay-Evidence/1.0','Accept':'application/json'})
    for attempt in range(3):
        try:
            with opener(req,timeout=30) as response: data=response.read(4_000_001)
            if len(data)>4_000_000: raise ValueError('Oversized ESPN response')
            return json.loads(data)
        except (TimeoutError, OSError):
            if attempt==2: raise
            time.sleep(attempt+1)

def extract_player_evidence(payload):
    """ESPN boxscore categories retain stat labels, values, player IDs, and team IDs.
    No unsupported assumptions about ordering or metric equivalence."""
    result=[]
    for group in ((payload.get('boxscore') or {}).get('players') or []):
        t=group.get('team') or {}
        for category in group.get('statistics') or []:
            labels=category.get('labels') or []
            if not isinstance(labels,list): continue
            for item in category.get('athletes') or []:
                athlete=item.get('athlete') or {}
                values=item.get('stats') or []
                if not isinstance(values,list) or len(labels)!=len(values): continue
                result.append({'player_id':str(athlete.get('id') or ''),'player_name':athlete.get('displayName'),'team':team(t.get('abbreviation')),'category':category.get('name'),'stats':dict(zip(labels,values))})
    return result

def check_game(snapshot,game):
    if not game: return 'GAME_NOT_FOUND'
    if not game.get('completed'): return 'NOT_FINAL'
    if not all(str(game[x].get('score','')).isdigit() for x in ('home','away')): return 'INVALID_FINAL_SCORE'
    if team(snapshot.get('home_team'))!=team(game['home']['team']) or team(snapshot.get('away_team'))!=team(game['away']['team']): return 'TEAM_MISMATCH'
    return 'FINAL_VERIFIED'

def build_report(snaps,games,summary_fetch=fetch_summary):
    results=[]; counts=Counter()
    for snap in snaps:
        gid=str(snap.get('game_id') or '')
        game=games.get(gid)
        status=check_game(snap,game)
        entry={'game_id':gid,'status':status,'pick_count':len(snap.get('picks') or []),'player_stat_records':0,'categories':[]}
        if status=='FINAL_VERIFIED':
            try:
                payload=summary_fetch(gid)
                records=extract_player_evidence(payload)
                entry['player_stat_records']=len(records)
                entry['categories']=sorted({str(r['category']) for r in records})
                if not records: entry['status']='NO_BOX_SCORE_RECORDS'
            except (OSError,ValueError,KeyError,TypeError) as exc:
                entry['status']='BOX_SCORE_UNAVAILABLE'
                entry['error_type']=type(exc).__name__
        counts[entry['status']]+=1
        results.append(entry)
    return {'mode':'READ_ONLY_PER_GAME_PLAYER_EVIDENCE','game_count':len(results),'counts':dict(counts),'games':results,'database_writes':0,'official_grades_written':0,'readiness':'BLOCKED_PENDING_VERIFIED_STAT_MAPPING_BETTING_CONTRACT_AND_WRITE_APPROVAL'}

def main():
    season=int(os.getenv('NFL_SEASON','2026')); week=int(os.getenv('NFL_WEEK','9'))
    snaps=get_rows(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],'nfl_prediction_snapshots',{'select':'season,week,game_id,home_team,away_team,picks','season':f'eq.{season}','week':f'eq.{week}','limit':'1000'})
    games=normalize_games(fetch_scoreboard(season,week))
    report=build_report(snaps,games)
    report.update({'season':season,'week':week,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    out=pathlib.Path('package5-output');out.mkdir(exist_ok=True)
    (out/'game_stats_evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'season':season,'week':week,'counts':report['counts'],'database_writes':0}))
if __name__=='__main__':main()
