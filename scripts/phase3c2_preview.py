#!/usr/bin/env python3
"""Read-only preview of browser-model-equivalent formulas; parity NOT certified.
No DB writes. Does not use manual sportsbook lines or generate official snapshots.
"""
import csv,io,json,math,os,sys,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).parent
BASE=json.loads((ROOT/'phase3c2_model_baselines.json').read_text())
TZ=ZoneInfo('America/New_York')

def clamp(lo,hi,v): return max(lo,min(hi,v))
def sigmoid(v): return 1/(1+math.exp(-clamp(-500,500,v)))
def num(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (ValueError,TypeError):return None

def fetch():
    url=os.environ['SUPABASE_URL'].rstrip('/')
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    q=urllib.parse.urlencode({'select':'season,generated_at,record_count,csv_text','season':'eq.2026','limit':'1'})
    req=urllib.request.Request(url+'/rest/v1/nfl_stat_exports?'+q,headers={'apikey':key,'Authorization':'Bearer '+key})
    with urllib.request.urlopen(req,timeout=45) as f: result=json.load(f)
    if len(result)!=1:raise ValueError('Expected exactly one season export')
    return result[0]

def kickoff(row):
    d=row.get('game_date','').strip(); t=row.get('game_time','').strip().upper()
    if not d or not t:return None
    for fmt in ('%H:%M','%H:%M:%S','%I:%M %p','%I:%M%p'):
        try:
            tm=datetime.strptime(t.replace(' ET','').replace(' EST','').replace(' EDT',''),fmt).time()
            dt=datetime.fromisoformat(d[:10]); local=dt.replace(hour=tm.hour,minute=tm.minute,second=tm.second,tzinfo=TZ)
            if local.replace(fold=0).utcoffset()!=local.replace(fold=1).utcoffset():return None
            if local.astimezone(timezone.utc).astimezone(TZ).replace(tzinfo=None)!=local.replace(tzinfo=None):return None
            return local.astimezone(timezone.utc)
        except ValueError:pass
    return None

def team_baselines():
    scores={k:dict(pf=0,pa=0,n=0) for k in BASE['teams']}
    for home,away,hs,aws in BASE['completed_scores']:
        for team,scored,allowed in ((home,hs,aws),(away,aws,hs)):
            x=scores[team];x['pf']+=scored;x['pa']+=allowed;x['n']+=1
    for team,x in scores.items():
        wins,losses=BASE['teams'][team][1:]
        x['ppg']=(x['pf']+22.5*3)/(x['n']+3)
        x['opp']=(x['pa']+22.5*3)/(x['n']+3)
        x['rt']=(wins/(wins+losses)-.5)*12+(x['ppg']-x['opp'])*.35
    return scores

def preview():
    export=fetch();raw=export['csv_text'];reader=csv.DictReader(io.StringIO(raw));rows=list(reader)
    required={'season','week','game_status','game_date','game_time','player_id','player','team','opponent_team','home_away','passing_yards','rushing_yards','touchdowns'}
    if missing:=required-set(reader.fieldnames or []):raise ValueError('Missing CSV fields: '+', '.join(sorted(missing)))
    if export.get('record_count') is not None and int(export['record_count'])!=len(rows):raise ValueError('Row count mismatch')
    hist=defaultdict(list);games=defaultdict(list)
    for row in rows:
        if row['season'].strip()!='2026':raise ValueError('Unexpected season')
        if row['game_status'].upper()=='COMPLETED':hist[(row['team'],''.join(c for c in row['player'].lower() if c.isalnum()))].append(row)
        elif row['game_status'].upper()=='SCHEDULED':
            team,opp,venue=row['team'],row['opponent_team'],row['home_away']
            if venue not in ('HOME','AWAY') or not team or not opp or team==opp:continue
            home,away=(team,opp) if venue=='HOME' else (opp,team)
            games[(int(row['week']),away,home)].append(row)
    now=datetime.now(timezone.utc); S=team_baselines(); output=[];blocked=[]
    for (week,away,home),future in sorted(games.items()):
        stamps={((r.get('game_date') or '').strip(),(r.get('game_time') or '').strip()) for r in future}
        start=kickoff(future[0]) if len(stamps)==1 else None
        reason=None
        if not start:reason='missing, ambiguous or inconsistent kickoff'
        elif start<=now:reason='kickoff already passed'
        elif start>now+timedelta(days=14):reason='more than 14 days away'
        elif away not in S or home not in S:reason='team absent from bundled model'
        if reason:blocked.append({'week':week,'game':away+' @ '+home,'reason':reason});continue
        margin=S[home]['rt']-S[away]['rt']+2
        total=(S[home]['ppg']+S[away]['opp'])/2+(S[away]['ppg']+S[home]['opp'])/2
        for market,pool in BASE['player_pools'].items():
            for team,name,season_total in pool:
                if team not in (away,home):continue
                key=(team,''.join(c for c in name.lower() if c.isalnum()))
                logs=sorted((r for r in hist[key] if int(r['week'])<week),key=lambda r:int(r['week']),reverse=True)
                field={'ps':'passing_yards','ru':'rushing_yards','td':'touchdowns'}[market]
                vals=[v for r in logs if (v:=num(r.get(field))) is not None]
                games_played=sum(BASE['teams'][team][1:])
                if not games_played:continue
                original=season_total/games_played
                # Browser sourcePlayer averages all earlier completed rows, then blends with bundled player average.
                v=(sum(vals)/len(vals)+original)/2 if vals else original
                own_margin=margin if team==home else -margin
                own_pts=total/2+own_margin/2
                scale=own_pts/S[team]['ppg']
                if market=='td':
                    base_proj=v*scale; baseline=None
                elif market=='ps':
                    base_proj=v*(.6+.4*scale)*(1-.006*own_margin);baseline=math.floor(v)+.5
                else:
                    base_proj=v*(1+.01*own_margin)*(.85+.15*scale);baseline=math.floor(v)+.5
                opp=away if team==home else home
                defense=clamp(.85,1.15,S[opp]['opp']/22.5)
                last5=sum(vals[:5])/min(5,len(vals)) if vals else None
                recent=1 if last5 is None or original<=0 else clamp(.8,1.2,last5/original)
                projection=max(0,base_proj*defense*(.75+.25*recent))
                if len(vals)>=3:
                    mean=sum(vals)/len(vals)
                    spread=max(1,math.sqrt(sum((z-mean)**2 for z in vals)/len(vals)))
                else:spread=max(.5 if market=='td' else 10,original*(.22 if market=='ps' else .38))
                probability=clamp(.05,.95,1-math.exp(-projection)) if baseline is None else clamp(.05,.95,sigmoid(1.7*(projection-baseline)/spread))
                score=(probability-.5)*100+(min(5,len(vals)) if len(vals)>=3 else 0)
                output.append({'week':week,'game':away+' @ '+home,'kickoff_utc':start.isoformat(),'player':name,'team':team,'market':market,'reference_line':baseline,'projection':round(projection,3),'model_over_probability':round(probability,5),'score':round(score,4),'historical_games':len(vals),'source':'bundled player baseline + available completed CSV logs','warning':'NOT parity-certified; roster and sportsbook line unverified'})
    output.sort(key=lambda p:(p['week'],-p['score'],p['player'],p['market']))
    report={'mode':'READ_ONLY_MODEL_PREVIEW','generated_utc':now.isoformat(),'export_generated_at':export.get('generated_at'),'row_count':len(rows),'candidate_count':len(output),'blocked_games':blocked,'model_parity':'UNVERIFIED — independent Python reproduction; browser cross-check required','limitations':['Only 2026 bundled player pool (12 passing, 12 rushing, 29 touchdown entries); not all CSV players','Uses static 2026 team records and scoring baseline from uploaded index.html','No browser-only manual sportsbook lines, so reference thresholds only','Player team assignments may be provisional; injuries and freshness not verified','Not a snapshot, not a backtest, no database writes'],'predictions':output}
    path=Path('phase3c2-report');path.mkdir(exist_ok=True)
    (path/'preview.json').write_text(json.dumps(report,indent=2))
    with (path/'preview.csv').open('w',newline='') as f:
        fields=['week','game','kickoff_utc','player','team','market','reference_line','projection','model_over_probability','score','historical_games','source','warning'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(output)
    print(json.dumps({k:report[k] for k in ('mode','generated_utc','export_generated_at','row_count','candidate_count','model_parity','limitations')},indent=2))
    for p in output[:20]:print('PREVIEW',p['week'],p['game'],p['player'],p['market'],'proj',p['projection'],'line',p['reference_line'],'prob',p['model_over_probability'])
    print('READ-ONLY: No Supabase writes; no archived snapshots created.')

if __name__=='__main__':
    try:preview()
    except Exception as exc:print('PREVIEW FAILED:',exc,file=sys.stderr);sys.exit(1)
