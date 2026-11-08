#!/usr/bin/env python3
"""3D22: read-only initial injury load preview. ESPN is unofficial; no DB writes."""
import csv, json, pathlib, urllib.request, urllib.error, datetime as dt, collections, hashlib, re
from urllib.parse import urlsplit
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path("phase3c3d22-report");OUT.mkdir(exist_ok=True)
INJ="https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
SCORE="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
TEAMS={'1':'ATL','2':'BUF','3':'CHI','4':'CIN','5':'CLE','6':'DAL','7':'DEN','8':'DET','9':'GB','10':'TEN','11':'IND','12':'KC','13':'LV','14':'LA','15':'MIA','16':'MIN','17':'NE','18':'NO','19':'NYG','20':'NYJ','21':'PHI','22':'ARI','23':'PIT','24':'LAC','25':'SF','26':'SEA','27':'TB','28':'WAS','29':'CAR','30':'JAC','33':'BAL','34':'HOU'}
def team(s):return {'JAX':'JAC','LAR':'LA','WSH':'WAS','OAK':'LV','SD':'LAC'}.get(str(s or '').upper(),str(s or '').upper())
def ts(s):
 try:
  x=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'))
  return x.astimezone(dt.timezone.utc) if x.tzinfo else None
 except (ValueError,TypeError,OverflowError):return None
def athlete_id(a):
 if not isinstance(a,dict):return ''
 if re.fullmatch(r'\d+',str(a.get('id',''))):return str(a['id'])
 refs=[a.get(k) for k in ('$ref','href','url')]+[v.get('href') for v in a.get('links',[]) if isinstance(v,dict)] if isinstance(a.get('links',[]),list) else []
 for ref in refs:
  if not isinstance(ref,str):continue
  path=urlsplit(ref).path
  for pat in (r'/athletes/(\d+)(?:/|$)',r'/nfl/player/_/id/(\d+)(?:/|$)',r'/nfl/player/(?:stats|splits)/_/id/(\d+)(?:/|$)'):
   m=re.search(pat,path)
   if m:return m.group(1)
 return ''
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'NFL-Parlay-ReadOnly-3D22/1.0','Accept':'application/json'},method='GET')
 with urllib.request.urlopen(req,timeout=35) as response:raw=response.read(12_000_000)
 return json.loads(raw),hashlib.sha256(raw).hexdigest()
def main():
 now=dt.datetime.now(dt.timezone.utc)
 with (ROOT/'phase3c3d12_player_game_evidence.csv').open(newline='',encoding='utf-8') as f: refs=list(csv.DictReader(f))
 audit={'phase':'3C-3D22','mode':'READ_ONLY_INITIAL_LOAD_PREVIEW','generated_utc':now.isoformat(),'reference_players':len(refs),'source_fetch_ok':False,'parser_validation':'NOT_RUN','schedule_validation':'NOT_RUN','db_access':'NONE','db_writes':0,'db_deletes':0,'snapshot_approvals':0,'rls_audit':'MANUALLY_VERIFIED_IN_PRIOR_STEP_NOT_RECHECKED','warnings':[]}
 feed={}; schedule={}; failures=[]
 try:
  data,digest=get(INJ)
  groups=data.get('injuries',[])
  if not isinstance(groups,list):raise ValueError('Unexpected injury groups')
  audit['injury_feed_sha256']=digest
  audit['injury_team_groups']=len(groups)
  audit['injury_raw_items']=sum(len(g.get('injuries',[])) for g in groups if isinstance(g,dict) and isinstance(g.get('injuries',[]),list))
  for group in groups:
   if not isinstance(group,dict):continue
   groupteam=TEAMS.get(str(group.get('id','')),'')
   for item in group.get('injuries',[]):
    if not isinstance(item,dict):continue
    a=item.get('athlete') or {}
    if not isinstance(a,dict):continue
    pid=athlete_id(a)
    t=a.get('team') or {}
    actualteam=team(t.get('abbreviation') if isinstance(t,dict) else '') or groupteam
    status=item.get('status') or ''
    if isinstance(status,dict):status=status.get('name') or status.get('displayName') or ''
    if pid:feed.setdefault(pid,[]).append({'team':actualteam,'group_team':groupteam,'name':a.get('displayName',''),'status':str(status),'updated':str(item.get('date') or '')})
  audit['injury_parsed_items']=sum(len(x) for x in feed.values())
  audit['source_fetch_ok']=True
  audit['parser_validation']='PASS' if audit['injury_parsed_items']>0 and audit['injury_parsed_items']==audit['injury_raw_items'] else 'FAIL'
 except Exception as e:
  audit['parser_validation']='FAIL'
  failures.append('Injury feed error: '+type(e).__name__+': '+str(e)[:140])
 # Verify each game by an explicitly identified season/week ESPN scoreboard event.
 # A game is valid only if event id, both team codes and kickoff all match.
 years=sorted({ts(p['kickoff_utc']).year for p in refs if ts(p['kickoff_utc'])})
 for year in years:
  for seasontype,weeks in ((2,range(1,19)),(3,range(1,6))):
   for week in weeks:
    url=f"{SCORE}?dates={year}&seasontype={seasontype}&week={week}&limit=100"
    try:
     payload,_=get(url)
     for ev in payload.get('events',[]) or []:
      eid=str(ev.get('id',''))
      if not eid:continue
      comp=(ev.get('competitions') or [{}])[0]
      teams={team(x.get('team',{}).get('abbreviation')) for x in comp.get('competitors',[]) if isinstance(x,dict)}
      record={'season':year,'week':week,'season_type':seasontype,'game_id':eid,
        'kickoff':ev.get('date') or comp.get('date'),'teams':sorted(teams)}
      if eid in schedule and schedule[eid]!=record:
       failures.append('Conflicting schedule event for '+eid)
      else:schedule[eid]=record
    except Exception as e:failures.append(f'Schedule {year}/{seasontype}/{week}: {type(e).__name__}')
 audit['schedule_events_unique']=len(schedule)
 audit['schedule_requests_failed']=len([f for f in failures if f.startswith('Schedule')])
 audit['schedule_validation']='PARTIAL' if audit['schedule_requests_failed'] else 'COMPLETE'
 # 11 schema fields followed by explanatory audit columns; never import this CSV.
 fields=['season','week','game_id','player_id','player_name','team','designation','practice_status','source','source_updated_at','fetched_at','schedule_check','injury_check','review_reason','would_insert','official_inactive_verified']
 rows=[]
 for p in refs:
  pid=str(p['espn_player_id']);t=team(p['team']);g=schedule.get(str(p['game_id']))
  kickoff=ts(p['kickoff_utc'])
  if not g:sch='GAME_NOT_FOUND'
  elif not kickoff or not ts(g['kickoff']):sch='KICKOFF_UNVERIFIED'
  elif abs((kickoff-ts(g['kickoff'])).total_seconds())>60:sch='KICKOFF_MISMATCH'
  elif t not in g['teams'] or team(p['opponent']) not in g['teams'] or len(g['teams'])!=2:sch='TEAM_MISMATCH'
  else:sch='VERIFIED'
  all_matches=feed.get(pid,[])
  matches=[x for x in all_matches if x['team']==t and (not x['group_team'] or x['group_team']==t)]
  dates=[ts(x['updated']) for x in matches]; dates=[x for x in dates if x]
  updated=max(dates) if dates else None
  age=(now-updated).total_seconds()/3600 if updated else None
  statuses={x['status'] for x in matches}
  if audit['parser_validation']!='PASS':inj='PARSER_FAILURE'
  elif all_matches and len(matches)!=len(all_matches):inj='TEAM_CONFLICT'
  elif not matches:inj='NO_INJURY_RECORD'
  elif len(statuses)!=1:inj='STATUS_CONFLICT'
  elif age is None:inj='NO_SOURCE_TIMESTAMP'
  elif not 0<=age<=48:inj='STALE_OR_FUTURE'
  else:inj='RECENT_UNOFFICIAL'
  reason='SCHEDULE_'+sch if sch!='VERIFIED' else 'INJURY_'+inj if inj!='RECENT_UNOFFICIAL' else 'PREVIEW_ONLY_NOT_APPROVED'
  rows.append({'season':g['season'] if sch=='VERIFIED' else '', 'week':g['week'] if sch=='VERIFIED' else '',
   'game_id':p['game_id'],'player_id':pid,'player_name':p['player'],'team':t,
   'designation':next(iter(statuses)) if len(statuses)==1 else '', 'practice_status':'',
   'source':'ESPN_UNOFFICIAL_PREVIEW','source_updated_at':updated.isoformat() if updated else '',
   'fetched_at':now.isoformat(),'schedule_check':sch,'injury_check':inj,'review_reason':reason,
   'would_insert':'FALSE','official_inactive_verified':'FALSE'})
 with (OUT/'initial_load_preview_DO_NOT_IMPORT.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
 audit['schedule_check_counts']=dict(collections.Counter(r['schedule_check'] for r in rows))
 audit['injury_check_counts']=dict(collections.Counter(r['injury_check'] for r in rows))
 audit['fully_schedule_verified']=sum(r['schedule_check']=='VERIFIED' for r in rows)
 audit['fresh_injury_evidence']=sum(r['injury_check']=='RECENT_UNOFFICIAL' for r in rows)
 audit['eligible_for_write']=0
 audit['unique_composite_keys']=len({(r['season'],r['week'],r['game_id'],r['player_id']) for r in rows})
 audit['warnings']+=failures[:50]
 audit['warnings']+=['Read-only: NO Supabase requests, writes, inserts, deletes, or approvals.',
 'ESPN is unofficial and not an official inactive list. Recent/Active does not mean cleared.',
 'Missing/stale entries never cause deletions. No import-ready CSV or write proposal.',
 'Season/week is populated ONLY when game ID, kickoff, and both teams match ESPN scoreboard.',
 'NFL season/week cannot be inferred from calendar year or game ID alone.',
 'The reference is a fixed 41-player historical sample, not the entire league injury feed.']
 (OUT/'audit.json').write_text(json.dumps(audit,indent=2))
 (OUT/'schedule_evidence.json').write_text(json.dumps({'events':[{k:v for k,v in item.items() if k!='teams'}|{'teams':item['teams']} for item in schedule.values() if item['game_id'] in {p['game_id'] for p in refs}]},indent=2))
 print(json.dumps(audit,indent=2))
 if len(refs)!=41:raise SystemExit('Unexpected player reference count')
 if audit['parser_validation']!='PASS':raise SystemExit('Injury parser validation failed; report saved.')
if __name__=='__main__':main()
