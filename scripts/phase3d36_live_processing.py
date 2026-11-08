#!/usr/bin/env python3
"""Phase 3D36: live ESPN full-feed injury matching and game candidate evidence.
Strictly GET/HEAD, never generates or saves predictions, never writes to Supabase.
"""
import collections, datetime as dt, json, os, pathlib, re, urllib.parse, urllib.request
UTC=dt.timezone.utc
INJ='https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'
SCORE='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
TEAM_IDS={'1':'ATL','2':'BUF','3':'CHI','4':'CIN','5':'CLE','6':'DAL','7':'DEN','8':'DET','9':'GB','10':'TEN','11':'IND','12':'KC','13':'LV','14':'LA','15':'MIA','16':'MIN','17':'NE','18':'NO','19':'NYG','20':'NYJ','21':'PHI','22':'ARI','23':'PIT','24':'LAC','25':'SF','26':'SEA','27':'TB','28':'WAS','29':'CAR','30':'JAC','33':'BAL','34':'HOU'}
ALIASES={'JAX':'JAC','LAR':'LA','WSH':'WAS','OAK':'LV','SD':'LAC','STL':'LA'}
def team(v):
    v=str(v or '').upper();return ALIASES.get(v,v)
def timestamp(s):
    try:
        d=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return d.astimezone(UTC) if d.tzinfo else None
    except (ValueError,TypeError):return None
def fetch(url, headers=None):
    if url not in (INJ,SCORE) and not url.startswith('https://') : raise ValueError('HTTPS required')
    req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'NFL-Parlay-3D36-ReadOnly/1.0',**(headers or {})},method='GET')
    with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
def parse_injuries(data,now):
    if not isinstance(data,dict) or not isinstance(data.get('injuries'),list):raise ValueError('Unexpected injury feed')
    records=[]
    for group in data['injuries']:
        if not isinstance(group,dict):continue
        parent=TEAM_IDS.get(str(group.get('id')),'')
        for entry in group.get('injuries',[]) or []:
            if not isinstance(entry,dict):continue
            a=entry.get('athlete') or {};a=a if isinstance(a,dict) else {}
            t=a.get('team') or {};t=team(t.get('abbreviation')) if isinstance(t,dict) else ''
            pid=str(a.get('id') or '')
            if not pid:
                for link in a.get('links',[]) or []:
                    m=re.search(r'/(?:id|athletes)/(\d+)(?:/|$|\?)',str(link.get('href',''))) if isinstance(link,dict) else None
                    if m:pid=m.group(1);break
            raw=entry.get('status') or ''
            if isinstance(raw,dict):raw=raw.get('name') or raw.get('displayName') or ''
            stamp=timestamp(entry.get('date'))
            age=(now-stamp).total_seconds()/3600 if stamp else None
            reason=('missing_player_id' if not pid else 'team_conflict' if t and parent and t!=parent else
                    'missing_team' if not (t or parent) else 'missing_status' if not str(raw).strip() else
                    'missing_timestamp' if age is None else 'stale_or_future' if age<0 or age>48 else None)
            records.append({'player_id':pid,'team':t or parent,'status':str(raw),'source_updated_at':stamp.isoformat() if stamp else None,
                            'eligible_evidence':reason is None,'hold_reason':reason})
    return records
def parse_games(data,now):
    if not isinstance(data,dict) or not isinstance(data.get('events'),list):raise ValueError('Unexpected schedule feed')
    games=[]
    for e in data['events']:
        if not isinstance(e,dict):continue
        comps=e.get('competitions') or [];competitors=comps[0].get('competitors',[]) if comps and isinstance(comps[0],dict) else []
        sides={}
        for c in competitors:
            if not isinstance(c,dict):continue
            obj=c.get('team') or {};sides[c.get('homeAway')]=team(obj.get('abbreviation')) if isinstance(obj,dict) else ''
        kickoff=timestamp(e.get('date'))
        valid=bool(e.get('id') and kickoff and sides.get('home') and sides.get('away') and sides['home']!=sides['away'])
        games.append({'game_id':str(e.get('id') or ''),'home':sides.get('home'),'away':sides.get('away'),
                      'kickoff_at':kickoff.isoformat() if kickoff else None,'identity_complete':valid,
                      'pregame_window':bool(valid and kickoff>now), 'kickoff_independently_verified':False})
    return games
def match(records,games):
    # Ambiguous schedules and stale injuries are NEVER approved automatically.
    by_team=collections.defaultdict(list)
    for g in games:
        if g['identity_complete'] and g['pregame_window']:
            for t in (g['home'],g['away']):by_team[t].append(g)
    matches=[]
    for r in records:
        choices=by_team.get(r['team'],[])
        reason=r['hold_reason'] or ('no_upcoming_game' if not choices else 'ambiguous_upcoming_games' if len(choices)!=1 else None)
        matches.append({'player_id':r['player_id'],'team':r['team'],'status':r['status'],
                        'game_id':choices[0]['game_id'] if len(choices)==1 else None,
                        'source_updated_at':r['source_updated_at'],'decision':'REVIEW_ONLY' if reason is None else 'HOLD',
                        'reason':reason,'game_day_inactive_verified':False})
    return matches
def validate_supabase_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or not re.fullmatch(r'[a-z0-9-]+\.supabase\.co',p.hostname or '') or p.path not in ('','/') or p.query or p.fragment:raise ValueError('Invalid Supabase URL')
    return url.rstrip('/')
def existing_injury_count():
    url=os.getenv('SUPABASE_URL');key=os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:return None
    url=validate_supabase_url(url)
    req=urllib.request.Request(url+'/rest/v1/nfl_player_injuries?select=*&limit=0',method='HEAD',headers={
        'apikey':key,'Authorization':'Bearer '+key,'Prefer':'count=exact','Range':'0-0'})
    with urllib.request.urlopen(req,timeout=30) as r:count=r.headers.get('Content-Range','').rsplit('/',1)[-1]
    if not count.isdigit():raise ValueError('Count unavailable')
    return int(count)
def main():
    now=dt.datetime.now(UTC);report={'phase':'3D36','mode':'READ_ONLY','generated_utc':now.isoformat(),'writes':0,
       'authentic_predictions_generated':0,'grades_calculated':0,'limitations':['ESPN feed is not official game-day inactives',
       'Scoreboard endpoint may only include a limited date window','No independent kickoff confirmation','No player stats/model inference in this phase'],
       'errors':[]}
    try:
        injuries=parse_injuries(fetch(INJ),now);games=parse_games(fetch(SCORE),now);matched=match(injuries,games)
        report.update({'injury_records':len(injuries),'injury_with_id':sum(bool(x['player_id']) for x in injuries),
          'injury_status_counts':dict(collections.Counter(x['status'] for x in injuries)),
          'games':len(games),'upcoming_games':sum(x['pregame_window'] for x in games),
          'candidate_review_only':sum(x['decision']=='REVIEW_ONLY' for x in matched),
          'held':sum(x['decision']=='HOLD' for x in matched),
          'hold_reasons':dict(collections.Counter(x['reason'] for x in matched if x['reason'])),
          'snapshot_candidates_authorized':0,'grade_candidates_authorized':0})
        report['existing_injury_rows']=existing_injury_count()
        # No player names or private database records in the uploaded artifact.
    except Exception as exc:report['errors'].append(type(exc).__name__+': '+str(exc)[:150])
    report['success']=not report['errors']
    pathlib.Path('phase3d36_live_processing_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['success']:raise SystemExit(1)
if __name__=='__main__':main()
