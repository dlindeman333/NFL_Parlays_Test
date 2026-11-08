#!/usr/bin/env python3
"""Consolidated market-aware read-only grading. Fail closed on ambiguous markets."""
import datetime as dt
import json
import os
import pathlib
from collections import Counter
from nfl_package3_live_audit import get_rows
from nfl_package4_final_evidence import fetch_scoreboard, normalize_games
from nfl_package5_game_stats import check_game, extract_player_evidence, fetch_summary, team
from nfl_package7_integrated_preview import grade_compound

VALID = {'HIT','MISS','PUSH'}

def grade_moneyline(pick, game):
    if pick.get('market') != 'ml' or pick.get('side') not in ('h','a'):
        return {'status':'UNAVAILABLE','reason':'Unsupported moneyline contract'}
    home, away = game['home'], game['away']
    try:
        hs, ans = int(home['score']), int(away['score'])
    except (KeyError,ValueError,TypeError):
        return {'status':'UNAVAILABLE','reason':'Invalid final scores'}
    if hs < 0 or ans < 0: return {'status':'UNAVAILABLE','reason':'Negative score'}
    if hs == ans: return {'status':'UNAVAILABLE','reason':'Tied final score requires market-specific settlement rules'}
    winner = 'h' if hs > ans else 'a'
    return {'status':'HIT' if winner == pick['side'] else 'MISS', 'actual_winner':winner,'home_score':hs,'away_score':ans,'market':'ml'}

def grade_pick(pick, game, records):
    if not isinstance(pick,dict): return {'status':'UNAVAILABLE','reason':'Invalid pick JSON'}
    if pick.get('market') == 'ml': return grade_moneyline(pick,game)
    if pick.get('market') == 'player' and pick.get('stat') == 'touchdowns':
        return {'status':'UNAVAILABLE','reason':'Touchdowns definition not verified (anytime scorer vs passing TD vs total TD)'}
    return grade_compound(pick,records)

def evaluate(snaps,games,summary_fetch=fetch_summary):
    counts=Counter(); games_count=Counter(); details=[]; market_counts=Counter()
    for snap in snaps:
        gid=str(snap.get('game_id') or '')
        game=games.get(gid)
        state=check_game(snap,game)
        picks=snap.get('picks')
        if not isinstance(picks,list):
            games_count['INVALID_PICKS_JSON']+=1;continue
        records=[]
        if state=='FINAL_VERIFIED' and any(isinstance(p,dict) and p.get('market')=='player' and p.get('stat')!='touchdowns' for p in picks):
            try:
                records=extract_player_evidence(summary_fetch(gid))
                if not records: state='NO_BOX_SCORE_RECORDS'
            except (OSError,ValueError,KeyError,TypeError):state='BOX_SCORE_UNAVAILABLE'
        games_count[state]+=1
        for i,p in enumerate(picks):
            market_counts[str(p.get('market')) if isinstance(p,dict) else 'invalid']+=1
            # A verified final score suffices for moneyline, even if boxscore is missing.
            final=check_game(snap,game)=='FINAL_VERIFIED'
            if not final: r={'status':'UNAVAILABLE','reason':'Game evidence: '+check_game(snap,game)}
            elif isinstance(p,dict) and p.get('market')=='ml':r=grade_moneyline(p,game)
            elif state!='FINAL_VERIFIED':r={'status':'UNAVAILABLE','reason':'Player evidence: '+state}
            else:r=grade_pick(p,game,records)
            counts[r['status']]+=1
            details.append({'game_id':gid,'pick_index':i,**r})
    return {'mode':'READ_ONLY_MARKET_AWARE_GRADING','game_counts':dict(games_count),'market_counts':dict(market_counts),'grade_counts':dict(counts),'picks_evaluated':len(details),'results':details,'database_writes':0,'official_grades_written':0,'readiness':'BLOCKED_PENDING_TOUCHDOWN_CONTRACT_VERIFICATION_BACKUP_AND_WRITE_APPROVAL','limitations':['Touchdowns cannot be graded without exact bet definition','No official grading writes','No historical snapshot changes','Game final evidence required for every settled pick']}

def main():
    season=int(os.getenv('NFL_SEASON','2026'));week=int(os.getenv('NFL_WEEK','9'))
    if not 2020<=season<=2100 or not 1<=week<=22:raise ValueError('Invalid season/week')
    snaps=get_rows(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],'nfl_prediction_snapshots',{'select':'season,week,game_id,home_team,away_team,picks','season':f'eq.{season}','week':f'eq.{week}','limit':'1000'})
    report=evaluate(snaps,normalize_games(fetch_scoreboard(season,week)))
    report.update({'season':season,'week':week,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    out=pathlib.Path('package8-output');out.mkdir(exist_ok=True)
    (out/'market_aware_grading.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('season','week','game_counts','grade_counts','database_writes','readiness')}))
if __name__=='__main__':main()
