#!/usr/bin/env python3
"""Read-only ESPN final-score evidence + Supabase snapshot comparison. No writes."""
import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request
from collections import Counter
from nfl_package3_live_audit import get_rows

ESPN = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'

def fetch_scoreboard(season, week):
    qs=urllib.parse.urlencode({'dates':str(season),'seasontype':'2','week':str(week),'limit':'100'})
    req=urllib.request.Request(ESPN+'?'+qs,headers={'User-Agent':'NFL-Parlay-ReadOnly-Evidence/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=35) as response:
        data=response.read(5_000_001)
    if len(data)>5_000_000: raise ValueError('Scoreboard response too large')
    return json.loads(data)

def normalize_games(payload):
    games={}
    for event in payload.get('events',[]):
        game_id=str(event.get('id',''))
        comps=(event.get('competitions') or [])
        comp=comps[0] if comps else {}
        competitors=comp.get('competitors') or []
        teams={}
        for c in competitors:
            role=c.get('homeAway')
            if role in ('home','away'):
                teams[role]={'team':str((c.get('team') or {}).get('abbreviation','')).upper(), 'score':c.get('score')}
        status=(event.get('status') or {}).get('type') or {}
        completed=status.get('completed') is True
        if not game_id or 'home' not in teams or 'away' not in teams: continue
        games[game_id]={'game_id':game_id,'completed':completed,'status':status.get('name'), 'home':teams['home'],'away':teams['away']}
    return games

def evaluate(snaps, games, season, week):
    rows=[]; counts=Counter()
    for s in snaps:
        game_id=str(s.get('game_id') or '')
        game=games.get(game_id)
        if not game: state='GAME_NOT_FOUND'
        elif not game['completed']: state='NOT_FINAL'
        elif not all(str(game[x].get('score','')).isdigit() for x in ('home','away')): state='INVALID_FINAL_SCORE'
        elif {str(s.get('home_team','')).upper(),str(s.get('away_team','')).upper()} != {game['home']['team'],game['away']['team']}: state='TEAM_MISMATCH'
        elif str(s.get('home_team','')).upper()!=game['home']['team']: state='HOME_AWAY_MISMATCH'
        else: state='FINAL_SCORE_VERIFIED'
        counts[state]+=1
        rows.append({'game_id':game_id,'status':state,'final_score':{'home':game['home']['score'],'away':game['away']['score']} if state=='FINAL_SCORE_VERIFIED' else None,'pick_count':len(s.get('picks') or [])})
    return {'mode':'READ_ONLY_FINAL_SCORE_EVIDENCE','season':season,'week':week,'snapshots':len(rows),'counts':dict(counts),'games':rows,'database_writes':0,'grading_writes':0,'readiness':'PLAYER_GAME_STATS_AND_MARKET_CONTRACT_STILL_REQUIRE_VERIFICATION'}

def main():
    season=int(os.getenv('NFL_SEASON','2026'));week=int(os.getenv('NFL_WEEK','9'))
    snaps=get_rows(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],'nfl_prediction_snapshots',{'select':'season,week,game_id,home_team,away_team,picks','season':f'eq.{season}','week':f'eq.{week}','limit':'1000'})
    games=normalize_games(fetch_scoreboard(season,week))
    result=evaluate(snaps,games,season,week)
    result['source']='ESPN public scoreboard API';result['checked_at_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    out=pathlib.Path('package4-output');out.mkdir(exist_ok=True)
    (out/'final_evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('season','week','snapshots','counts','database_writes','readiness')}))
if __name__=='__main__':main()
