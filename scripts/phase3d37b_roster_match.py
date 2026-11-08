#!/usr/bin/env python3
"""Read-only ESPN roster/schedule verification; no Supabase credentials or writes."""
import argparse, csv, io, json, os, sys, time
from collections import defaultdict
from datetime import datetime, timezone
from urllib.request import Request, urlopen

BASE='https://site.api.espn.com/apis/site/v2/sports/football/nfl'
def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'NFLParlayReadOnlyAudit/1.0','Accept':'application/json'}),timeout=25) as r:
        return json.load(r)
def teams(data):
    leagues=data.get('sports',[])
    entries=[]
    for league in leagues:
        for l in league.get('leagues',[]): entries+=l.get('teams',[])
    return [x.get('team',x) for x in entries]
def athletes(data):
    result=[]
    for group in data.get('athletes',[]):
        result+=group.get('items',[]) if isinstance(group,dict) else []
    return result
def games(data):
    result=[]
    for e in data.get('events',[]):
        comps=(e.get('competitions') or [{}])[0]
        competitors=comps.get('competitors',[])
        ids=[str(x.get('team',{}).get('id','')) for x in competitors]
        if len(ids)!=2 or not e.get('date') or not e.get('id'): continue
        result.append({'game_id':str(e['id']),'kickoff_at':e['date'],'team_ids':ids,'status':e.get('status',{}).get('type',{}).get('name','')})
    return result
def parse_dt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def verify(roster_index, events, now):
    by_team=defaultdict(list)
    for e in events:
        try: kickoff=parse_dt(e['kickoff_at'])
        except (ValueError,TypeError): continue
        if kickoff<=now: continue
        for tid in e['team_ids']: by_team[tid].append(e)
    matches=[]
    for player_id, records in roster_index.items():
        unique={r['team_id'] for r in records}
        if len(unique)!=1:
            matches.append({'player_id':player_id,'status':'ambiguous_roster','team_ids':sorted(unique)});continue
        tid=next(iter(unique))
        upcoming=sorted(by_team.get(tid,[]),key=lambda x:x['kickoff_at'])
        if not upcoming:
            matches.append({'player_id':player_id,'status':'no_upcoming_game','team_id':tid});continue
        game=upcoming[0]
        matches.append({'player_id':player_id,'status':'matched','team_id':tid,'game_id':game['game_id'],'kickoff_at':game['kickoff_at'],'opponent_team_id':next(x for x in game['team_ids'] if x!=tid)})
    return matches
def main():
    p=argparse.ArgumentParser();p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int,required=True);p.add_argument('--output',default='phase3d37b_report.json');args=p.parse_args()
    # Fetch all 32 teams and current rosters, then a season/week-specific scoreboard.
    team_list=teams(fetch(BASE+'/teams?limit=50'))
    if len(team_list)!=32: raise RuntimeError(f'Expected 32 teams; got {len(team_list)}. Fail closed.')
    roster_index=defaultdict(list);failures=[]
    for t in team_list:
        tid=str(t['id'])
        try:
            for a in athletes(fetch(BASE+f'/teams/{tid}/roster')):
                if a.get('id'): roster_index[str(a['id'])].append({'team_id':tid})
        except Exception as ex: failures.append({'team_id':tid,'error':type(ex).__name__})
        time.sleep(.12)
    schedule=games(fetch(BASE+f'/scoreboard?dates={args.season}&week={args.week}&seasontype=2&limit=1000'))
    now=datetime.now(timezone.utc)
    matches=verify(roster_index,schedule,now)
    statuses=defaultdict(int)
    for m in matches: statuses[m['status']]+=1
    report={'season':args.season,'week':args.week,'run_at_utc':now.isoformat(),'source':'ESPN public site endpoints (unofficial)','teams':len(team_list),'roster_fetch_failures':failures,'players_seen':len(roster_index),'games_found':len(schedule),'status_counts':dict(statuses),'sample_matches':[x for x in matches if x['status']=='matched'][:12],'writes_enabled':False,'supabase_accessed':False,'authentic_predictions_created':0,'notes':['Current rosters are NOT historical point-in-time rosters.','No stats export was read; projections are not generated.','Unverified or missing IDs must be excluded from prediction generation.']}
    with open(args.output,'w') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:report[k] for k in ('teams','players_seen','games_found','status_counts','writes_enabled')},indent=2))
    if failures or not schedule: sys.exit('Incomplete roster or schedule data: fail closed')
if __name__=='__main__':main()
