#!/usr/bin/env python3
"""Preview-only injury staging; no Supabase calls and no database writes."""
import csv, json, pathlib, urllib.request, datetime as dt, collections, re, hashlib
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d21-report'); OUT.mkdir(exist_ok=True)
URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'
TEAMS={'1':'ATL','2':'BUF','3':'CHI','4':'CIN','5':'CLE','6':'DAL','7':'DEN','8':'DET','9':'GB','10':'TEN','11':'IND','12':'KC','13':'LV','14':'LA','15':'MIA','16':'MIN','17':'NE','18':'NO','19':'NYG','20':'NYJ','21':'PHI','22':'ARI','23':'PIT','24':'LAC','25':'SF','26':'SEA','27':'TB','28':'WAS','29':'CAR','30':'JAC','33':'BAL','34':'HOU'}
def normalize(t):return {'JAX':'JAC','LAR':'LA','WSH':'WAS'}.get(str(t or '').upper(),str(t or '').upper())
def stamp(s):
 try:
  x=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'));return x.astimezone(dt.timezone.utc) if x.tzinfo else None
 except (ValueError,TypeError):return None
now=dt.datetime.now(dt.timezone.utc)
with (ROOT/'phase3c3d12_player_game_evidence.csv').open(newline='') as f: players=list(csv.DictReader(f))
audit={'phase':'3C-3D21','mode':'PREVIEW_ONLY','generated_utc':now.isoformat(),'reference_players':len(players),'supabase_access':'NONE','db_writes':0,'db_deletes':0,'snapshot_approvals':0,'source_fetch_ok':False,'proposed_inserts':0,'rls_verified':False,'constraints_verified':False,'warnings':[]}
feed={}; source_hash=''
try:
 req=urllib.request.Request(URL,headers={'User-Agent':'NFL-Parlay-ReadOnly-Audit/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=35) as r: raw=r.read(10000000)
 source_hash=hashlib.sha256(raw).hexdigest(); data=json.loads(raw)
 for group in data.get('injuries',[]):
  groupteam=TEAMS.get(str(group.get('id','')),'')
  for item in group.get('injuries',[]):
   a=item.get('athlete') or {}; t=a.get('team') or {}
   pid=str(a.get('id') or ''); team=normalize(t.get('abbreviation') or groupteam)
   if pid:feed.setdefault(pid,[]).append({'team':team,'name':a.get('displayName') or a.get('fullName') or '', 'status':str(item.get('status') or ''),'date':str(item.get('date') or ''),'group_team':groupteam})
 audit['source_fetch_ok']=True; audit['source_sha256']=source_hash; audit['source_records']=sum(map(len,feed.values()))
except Exception as e:audit['warnings'].append('Source fetch failed: '+type(e).__name__)
rows=[]
for p in players:
 pid=p['espn_player_id']; team=normalize(p['team']); matches=feed.get(pid,[])
 valid=[m for m in matches if m['team']==team and (not m['group_team'] or m['group_team']==team)]
 conflict=bool(matches and len(valid)!=len(matches))
 dates=[stamp(m['date']) for m in valid]; dates=[d for d in dates if d]
 recent=max(dates) if dates else None
 age=(now-recent).total_seconds()/3600 if recent else None
 statuses=sorted({m['status'] for m in valid})
 # Reference lacks season/week: do not guess. Preview is NOT import-ready.
 reason=('FEED_UNAVAILABLE' if not audit['source_fetch_ok'] else 'NO_MATCH' if not matches else 'TEAM_CONFLICT' if conflict else 'MULTIPLE_STATUSES' if len(statuses)>1 else 'MISSING_TIMESTAMP' if age is None else 'STALE_OR_FUTURE' if age<0 or age>48 else 'FRESH_EVIDENCE_REVIEW')
 rows.append({'season':'','week':'','game_id':p['game_id'],'player_id':pid,'player_name':p['player'],'team':team,'designation':statuses[0] if len(statuses)==1 else '', 'practice_status':'','source':'ESPN_UNOFFICIAL_PREVIEW','source_updated_at':recent.isoformat() if recent else '', 'fetched_at':now.isoformat(), 'review_reason':reason,'proposed_insert':False,'official_inactive_verified':False})
with (OUT/'initial_load_preview_NOT_FOR_IMPORT.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
audit['review_reasons']=dict(collections.Counter(r['review_reason'] for r in rows))
audit['reference_unique_keys']=len({(r['game_id'],r['player_id']) for r in rows})
audit['warnings']+=['season/week intentionally blank: must derive from authoritative schedule and verify before writes','ESPN is not an official inactive list; even fresh Active is not clearance','Manual SQL audit required to verify RLS, constraints and grants','No insert proposal authorized until database security and source freshness validated']
(OUT/'audit.json').write_text(json.dumps(audit,indent=2))
print(json.dumps(audit,indent=2))
if len(players)!=41:raise SystemExit('Reference count changed; review required')
if not audit['source_fetch_ok']:raise SystemExit('Source fetch failed; see artifact')
