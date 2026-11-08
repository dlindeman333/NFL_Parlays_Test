#!/usr/bin/env python3
"""Live read-only snapshot/stats audit. Never sends HTTP mutation requests."""
import csv, datetime as dt, io, json, os, pathlib, re, urllib.parse, urllib.request
from collections import Counter
from nfl_readonly_grader import grade_pick

MAX_BYTES=18_000_000

def get_rows(url,key,table,query):
    host=urllib.parse.urlsplit(url)
    if host.scheme!='https' or not re.fullmatch(r'[a-z0-9-]+\.supabase\.co',host.hostname or '') or host.path not in ('','/') or host.query or host.fragment or host.username:
        raise ValueError('Invalid Supabase URL')
    req=urllib.request.Request(url.rstrip('/')+'/rest/v1/'+table+'?'+urllib.parse.urlencode(query),headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'},method='GET')
    with urllib.request.urlopen(req,timeout=50) as r: data=r.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES: raise ValueError('Response too large')
    value=json.loads(data)
    if not isinstance(value,list): raise ValueError('Expected JSON array')
    return value

def inspect(snaps,rows,season,week):
    stats=[r for r in rows if str(r.get('season'))==str(season) and str(r.get('week'))==str(week)]
    summary=Counter(); reasons=Counter(); details=[]
    for s in snaps:
        if str(s.get('season'))!=str(season) or str(s.get('week'))!=str(week): continue
        game=str(s.get('game_id') or '')
        teams={str(s.get('home_team') or '').upper(),str(s.get('away_team') or '').upper()}
        picks=s.get('picks') or []
        if not isinstance(picks,list): summary['INVALID_SNAPSHOT']+=1;continue
        for idx,p in enumerate(picks):
            if not isinstance(p,dict): summary['UNAVAILABLE']+=1; reasons['Invalid pick JSON']+=1;continue
            team=str(p.get('team') or '').upper()
            # CSV has no game_id: verify player belongs to one of snapshot's teams.
            if team not in teams or not team:
                result={'status':'UNAVAILABLE','reason':'Pick team not verified against snapshot matchup'}
            else:
                result=grade_pick(p,stats)
            status=result['status']; summary[status]+=1
            if result.get('reason'): reasons[result['reason']]+=1
            details.append({'game_id':game,'pick_index':idx,'status':status,'reason':result.get('reason')})
    return {'mode':'LIVE_READ_ONLY_GRADING_AUDIT','season':season,'week':week,'snapshot_count':len(snaps),'stat_rows_for_week':len(stats),'total_picks':len(details),'grade_counts':dict(summary),'unavailable_reasons':dict(reasons),'results':details,'database_writes':0,'snapshot_writes':0,'grade_writes':0,'readiness':'REQUIRES_VALIDATED_FINAL_STATS_AND_WRITE_APPROVAL','limitations':['CSV does not contain canonical game_id; team and week checked','Player-name matching may be ambiguous; ambiguous records are not graded','No game-level score grading','No automatic prediction creation, grading writes, injury sync or schedule activation','Stats export may contain cumulative rather than single-game values; no writes authorized']}

def main():
    url=os.environ['SUPABASE_URL'];key=os.environ['SUPABASE_SERVICE_ROLE_KEY'];season=int(os.environ.get('NFL_SEASON','2026'));week=int(os.environ['NFL_WEEK'])
    snaps=get_rows(url,key,'nfl_prediction_snapshots',{'select':'season,week,game_id,home_team,away_team,picks','season':f'eq.{season}','week':f'eq.{week}','limit':'1000'})
    exports=get_rows(url,key,'nfl_stat_exports',{'select':'season,generated_at,csv_text','season':f'eq.{season}','order':'generated_at.desc','limit':'1'})
    if not exports or not isinstance(exports[0].get('csv_text'),str): raise ValueError('No CSV export available')
    stats=list(csv.DictReader(io.StringIO(exports[0]['csv_text'])))
    report=inspect(snaps,stats,season,week)
    report['evaluated_at_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    report['source_generated_at']=exports[0].get('generated_at')
    dest=pathlib.Path('package3-output');dest.mkdir(exist_ok=True)
    (dest/'grading_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('season','week','snapshot_count','total_picks','grade_counts','database_writes','readiness')}))
if __name__=='__main__':main()
