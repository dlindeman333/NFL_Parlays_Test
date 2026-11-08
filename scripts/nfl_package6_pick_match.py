#!/usr/bin/env python3
"""Conservative, read-only, per-game ESPN boxscore to archived player-pick matcher.
Never substitutes season totals or infers unavailable statistics.
"""
import datetime as dt
import json
import math
import os
import pathlib
from collections import Counter
from nfl_package3_live_audit import get_rows
from nfl_package4_final_evidence import fetch_scoreboard, normalize_games
from nfl_package5_game_stats import check_game, extract_player_evidence, fetch_summary, team

# ESPN boxscore categories and labels must both match. Some labels are compound.
MAP = {
 'pass_yards':('passing','YDS'), 'pass_tds':('passing','TD'),
 'pass_interceptions':('passing','INT'),
 'rush_attempts':('rushing','CAR'), 'rush_yards':('rushing','YDS'), 'rush_tds':('rushing','TD'),
 'receptions':('receiving','REC'), 'rec_yards':('receiving','YDS'), 'rec_tds':('receiving','TD'),
 'targets':('receiving','TGTS'),
}

def parse_number(v):
    if isinstance(v,bool): return None
    try:
        n=float(v)
        return n if math.isfinite(n) and n>=0 else None
    except (TypeError,ValueError): return None

def value_for(record,stat):
    category,label=MAP[stat]
    if str(record.get('category','')).lower()!=category: return None
    return parse_number((record.get('stats') or {}).get(label))

def grade(pick,records):
    if pick.get('market')!='player': return {'status':'UNAVAILABLE','reason':'Game market requires separately verified market contract'}
    stat=pick.get('stat'); side=pick.get('side')
    if stat not in MAP: return {'status':'UNAVAILABLE','reason':'Unsupported or compound stat'}
    if side not in ('o','u'): return {'status':'UNAVAILABLE','reason':'Unsupported side'}
    line=parse_number(pick.get('line'))
    if line is None: return {'status':'UNAVAILABLE','reason':'Invalid saved betting line'}
    name=str(pick.get('player_name') or '').strip().casefold()
    tm=team(pick.get('team'))
    if not name or not tm: return {'status':'UNAVAILABLE','reason':'Missing player identity'}
    matches=[r for r in records if str(r.get('player_name') or '').strip().casefold()==name and team(r.get('team'))==tm and str(r.get('category','')).lower()==MAP[stat][0]]
    if len(matches)!=1: return {'status':'UNAVAILABLE','reason':'Missing or ambiguous player/category match'}
    actual=value_for(matches[0],stat)
    if actual is None: return {'status':'UNAVAILABLE','reason':'Missing verified single-game statistic'}
    status='PUSH' if actual==line else 'HIT' if (actual>line if side=='o' else actual<line) else 'MISS'
    return {'status':status,'actual':actual,'line':line,'side':side,'stat':stat,'player_id':matches[0].get('player_id')}

def evaluate(snaps,games,summary_fetch=fetch_summary):
    details=[];counts=Counter();game_counts=Counter()
    for snap in snaps:
        gid=str(snap.get('game_id') or '')
        status=check_game(snap,games.get(gid))
        picks=snap.get('picks')
        if not isinstance(picks,list):
            game_counts['INVALID_PICKS_JSON']+=1;continue
        records=[]
        if status=='FINAL_VERIFIED':
            try: records=extract_player_evidence(summary_fetch(gid))
            except (OSError,ValueError,TypeError,KeyError): status='BOX_SCORE_UNAVAILABLE'
            if not records and status=='FINAL_VERIFIED': status='NO_BOX_SCORE_RECORDS'
        game_counts[status]+=1
        for i,p in enumerate(picks):
            if status!='FINAL_VERIFIED': result={'status':'UNAVAILABLE','reason':'Game evidence: '+status}
            elif not isinstance(p,dict): result={'status':'UNAVAILABLE','reason':'Invalid pick JSON'}
            else: result=grade(p,records)
            counts[result['status']]+=1
            details.append({'game_id':gid,'pick_index':i,**result})
    return {'mode':'READ_ONLY_PER_GAME_PICK_MATCH','game_counts':dict(game_counts),'grade_counts':dict(counts),'picks_evaluated':len(details),'results':details,'database_writes':0,'official_grades_written':0,'readiness':'PREVIEW_ONLY_REQUIRES_SOURCE_CONTRACT_REVIEW_BACKUP_AND_EXPLICIT_WRITE_APPROVAL','limitations':['Only unambiguous player/category/name/team matches','No composite passing C/ATT, combined TDs, or game markets','No automatic writes or scheduling','ESPN category label equivalence requires validation against actual boxscores']}

def main():
    season=int(os.environ.get('NFL_SEASON','2026'));week=int(os.environ.get('NFL_WEEK','9'))
    if not 2020<=season<=2100 or not 1<=week<=22: raise ValueError('Invalid season/week')
    snaps=get_rows(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],'nfl_prediction_snapshots',{'select':'season,week,game_id,home_team,away_team,picks','season':f'eq.{season}','week':f'eq.{week}','limit':'1000'})
    result=evaluate(snaps,normalize_games(fetch_scoreboard(season,week)))
    result.update({'season':season,'week':week,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    path=pathlib.Path('package6-output');path.mkdir(exist_ok=True)
    (path/'pick_match_preview.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('season','week','game_counts','grade_counts','database_writes','readiness')}))
if __name__=='__main__':main()
