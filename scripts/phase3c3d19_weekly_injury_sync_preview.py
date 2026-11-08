#!/usr/bin/env python3
"""Phase 3C-3D19: read-only ESPN injury feed and optional Supabase comparison.
Only GET requests; no writes, approvals, or deletions. Source is NOT official NFL inactives.
"""
import csv, datetime as dt, hashlib, json, os, pathlib, re, urllib.parse, urllib.request
from collections import Counter

BASE=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path("phase3c3d19-report"); OUT.mkdir(exist_ok=True)
ESPN="https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
TEAM_IDS={'1':'ATL','2':'BUF','3':'CHI','4':'CIN','5':'CLE','6':'DAL','7':'DEN','8':'DET','9':'GB','10':'TEN','11':'IND','12':'KC','13':'LV','14':'LA','15':'MIA','16':'MIN','17':'NE','18':'NO','19':'NYG','20':'NYJ','21':'PHI','22':'ARI','23':'PIT','24':'LAC','25':'SF','26':'SEA','27':'TB','28':'WAS','29':'CAR','30':'JAC','33':'BAL','34':'HOU'}
def code(s): return {'JAX':'JAC','LAR':'LA','WSH':'WAS','OAK':'LV','SD':'LAC','STL':'LA'}.get(str(s or '').upper(),str(s or '').upper())
def norm(s): return re.sub(r'[^a-z0-9]','',re.sub(r'\b(jr|sr|ii|iii|iv|v)\b','',str(s or '').lower()))
def when(s):
    try:
        x=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return x.astimezone(dt.timezone.utc) if x.tzinfo else None
    except (ValueError,TypeError): return None
def get(url,headers=None):
    req=urllib.request.Request(url,headers={'User-Agent':'NFL-Parlay-Phase3D19-ReadOnly/1.0','Accept':'application/json',**(headers or {})},method='GET')
    with urllib.request.urlopen(req,timeout=35) as resp: raw=resp.read(10_000_000)
    return json.loads(raw),hashlib.sha256(raw).hexdigest()
def athlete_id(a):
    if a.get('id'): return str(a['id'])
    for link in a.get('links',[]) or []:
        if not isinstance(link,dict): continue
        m=re.search(r'/(?:id|athletes)/(\d+)(?:/|$|\?)',str(link.get('href','')))
        if m: return m.group(1)
    return ''
def parse_feed(data):
    rows=[]
    for group in data.get('injuries',[]) if isinstance(data,dict) else []:
        if not isinstance(group,dict): continue
        parent=TEAM_IDS.get(str(group.get('id','')),'')
        for item in group.get('injuries',[]) or []:
            if not isinstance(item,dict): continue
            athlete=item.get('athlete') or {}
            if not isinstance(athlete,dict): athlete={}
            team_obj=athlete.get('team') or {}
            team=code(team_obj.get('abbreviation','')) if isinstance(team_obj,dict) else ''
            status=item.get('status','')
            if isinstance(status,dict): status=status.get('name') or status.get('displayName') or ''
            rows.append({'team':team or parent,'player_id':athlete_id(athlete),
                'player':str(athlete.get('displayName') or athlete.get('fullName') or ''),
                'raw_status':str(status),'source_date':str(item.get('date') or ''),
                'team_conflict':bool(team and parent and team!=parent)})
    return rows
def safe_status(raw):
    x=str(raw).strip().lower()
    if x in ('out','out for season','injured reserve','ir'): return 'OUT_OR_IR'
    if x in ('questionable','doubtful'): return x.upper()
    if x in ('active','probable','day-to-day'): return 'UNVERIFIED_OTHER'
    return 'UNRECOGNIZED'
def db_read():
    url=os.getenv('SUPABASE_URL','').rstrip('/')
    key=os.getenv('SUPABASE_SERVICE_ROLE_KEY','')
    if not url or not key: return None,'NOT_CONFIGURED'
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.supabase.co') or parsed.username or parsed.password:
        return None,'INVALID_SUPABASE_URL'
    # Strictly GET, read-only, capped to 10,000 rows; do not assume column schema.
    collected=[]
    for start in range(0,10000,1000):
        endpoint=url+'/rest/v1/nfl_player_injuries?select=*&limit=1000&offset='+str(start)
        try:
            batch,_=get(endpoint,{'apikey':key,'Authorization':'Bearer '+key})
        except Exception as e: return None,'READ_ERROR_'+type(e).__name__
        if not isinstance(batch,list): return None,'UNEXPECTED_RESPONSE'
        collected.extend(batch)
        if len(batch)<1000: return collected,'READ_OK'
    return None,'ROW_CAP_REACHED'
def db_key(r):
    pid=next((str(r[k]) for k in ('espn_player_id','espn_id','player_id') if r.get(k) is not None and str(r[k]).strip()),'')
    team=code(r.get('team') or r.get('team_abbreviation') or '')
    return (pid,team) if pid and team else None
def main():
    now=dt.datetime.now(dt.timezone.utc)
    with (BASE/'phase3c3d12_player_game_evidence.csv').open(newline='',encoding='utf-8') as f: players=list(csv.DictReader(f))
    audit={'phase':'3C-3D19','mode':'READ_ONLY_WEEKLY_INJURY_SYNC_PREVIEW','generated_utc':now.isoformat(),
           'reference_players':len(players),'source':ESPN,'source_fetch_ok':False,'source_error':None,
           'supabase_read_state':'NOT_ATTEMPTED','db_writes':0,'db_deletes':0,'snapshot_approvals':0,
           'limitations':['ESPN injury endpoint is unofficial and may be incomplete or stale',
             'ESPN Active does not mean cleared for game day',
             'Missing feed entries must not delete database records',
             'No automatic database updates or prediction approvals',
             'DB column compatibility must be confirmed before any write-enabled phase']}
    feed=[]; digest=''
    try:
        data,digest=get(ESPN); feed=parse_feed(data)
        audit['source_fetch_ok']=True
        audit['source_sha256']=digest
        audit['source_timestamp']=data.get('timestamp') if isinstance(data,dict) else None
        audit['feed_team_groups']=len(data.get('injuries',[])) if isinstance(data,dict) else 0
    except Exception as e: audit['source_error']=type(e).__name__+': '+str(e)[:180]
    audit['feed_records']=len(feed)
    audit['feed_id_present']=sum(bool(r['player_id']) for r in feed)
    audit['feed_team_present']=sum(bool(r['team']) for r in feed)
    audit['feed_team_conflicts']=sum(r['team_conflict'] for r in feed)
    db,state=db_read(); audit['supabase_read_state']=state
    audit['supabase_rows_read']=len(db) if db is not None else None
    db_by_key={}
    if db is not None:
        for r in db:
            if not isinstance(r,dict): continue
            k=db_key(r)
            if k: db_by_key.setdefault(k,[]).append(r)
    audit['db_rows_with_usable_identity']=sum(map(len,db_by_key.values()))
    results=[]
    for p in players:
        pid=str(p.get('espn_player_id','')).strip(); team=code(p['team'])
        by_id=[r for r in feed if r['player_id']==pid] if pid else []
        selected=by_id or [r for r in feed if not r['player_id'] and r['team']==team and norm(r['player'])==norm(p['player'])]
        identity_conflict=any(r['team']!=team or r['team_conflict'] for r in selected)
        distinct={(r['team'],r['player_id'],norm(r['player'])) for r in selected}
        ambiguous=identity_conflict or len(distinct)>1
        dates=[when(r['source_date']) for r in selected]; dates=[x for x in dates if x]
        latest=max(dates) if dates else None
        age_hours=round((now-latest).total_seconds()/3600,1) if latest else None
        freshness='FRESH_48H' if age_hours is not None and 0<=age_hours<=48 else ('STALE_OR_FUTURE' if age_hours is not None else 'MISSING_TIMESTAMP')
        statuses=sorted({r['raw_status'] for r in selected})
        normalized=sorted({safe_status(s) for s in statuses})
        identity='CONFLICT' if ambiguous else ('ID_MATCH' if by_id else ('NAME_TEAM_FALLBACK' if selected else 'NO_FEED_RECORD'))
        if not audit['source_fetch_ok']: proposal='SOURCE_UNAVAILABLE_NO_CHANGE'
        elif not selected: proposal='MISSING_FEED_RECORD_NO_CHANGE'
        elif ambiguous: proposal='IDENTITY_CONFLICT_REVIEW'
        elif freshness!='FRESH_48H': proposal='STALE_OR_UNDATED_HOLD'
        elif len(normalized)!=1 or 'UNRECOGNIZED' in normalized: proposal='AMBIGUOUS_STATUS_HOLD'
        else: proposal='FRESH_CANDIDATE_REVIEW_ONLY'
        existing=db_by_key.get((pid,team),[]) if db is not None else []
        if db is None: comparison='DB_NOT_READ'
        elif not db_by_key and db: comparison='DB_SCHEMA_UNMAPPED'
        elif len(existing)>1: comparison='DUPLICATE_DB_ROWS_REVIEW'
        elif not existing: comparison='NO_MATCHING_DB_ROW'
        else:
            r=existing[0]
            old=next((str(r[k]) for k in ('status','injury_status','designation','raw_status') if r.get(k) is not None),'')
            comparison=('SAME_STATUS' if old.strip().lower() in {s.lower() for s in statuses} else 'STATUS_DIFFERENT') if old else 'DB_STATUS_COLUMN_UNKNOWN'
        results.append({'player':p['player'],'team':team,'espn_player_id':pid,'game_id':p['game_id'],
            'kickoff_utc':p['kickoff_utc'],'match_method':identity,'source_records':len(selected),
            'observed_statuses':' | '.join(statuses),'normalized_statuses':' | '.join(normalized),
            'latest_source_date':latest.isoformat() if latest else '', 'age_hours':age_hours if age_hours is not None else '',
            'freshness':freshness,'preview_decision':proposal,'db_comparison':comparison,
            'game_day_verified':False,'snapshot_approved':False})
    with (OUT/'player_sync_preview.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    with (OUT/'feed_structure_summary.json').open('w') as f:
        json.dump({'feed_records':len(feed),'team_counts':dict(Counter(r['team'] for r in feed)),
                   'status_counts':dict(Counter(r['raw_status'] for r in feed))},f,indent=2)
    audit['preview_counts']=dict(Counter(r['preview_decision'] for r in results))
    audit['comparison_counts']=dict(Counter(r['db_comparison'] for r in results))
    audit['game_day_verified']=0
    with (OUT/'audit.json').open('w') as f: json.dump(audit,f,indent=2)
    print(json.dumps(audit,indent=2))
    if len(players)!=41: raise SystemExit('Unexpected player reference count')
    if not audit['source_fetch_ok']: raise SystemExit('ESPN fetch failed; inspect artifact. No data modified.')
if __name__=='__main__': main()
