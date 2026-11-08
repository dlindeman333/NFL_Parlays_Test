#!/usr/bin/env python3
"""Phase 3D21C: expanded ESPN player profile link parser, preview only, no Supabase calls or writes."""
import csv, json, pathlib, urllib.request, datetime as dt, collections, re, hashlib
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d21c-report'); OUT.mkdir(exist_ok=True)
URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'
TEAMS={'1':'ATL','2':'BUF','3':'CHI','4':'CIN','5':'CLE','6':'DAL','7':'DEN','8':'DET','9':'GB','10':'TEN','11':'IND','12':'KC','13':'LV','14':'LA','15':'MIA','16':'MIN','17':'NE','18':'NO','19':'NYG','20':'NYJ','21':'PHI','22':'ARI','23':'PIT','24':'LAC','25':'SF','26':'SEA','27':'TB','28':'WAS','29':'CAR','30':'JAC','33':'BAL','34':'HOU'}
def normalize(t):return {'JAX':'JAC','LAR':'LA','WSH':'WAS'}.get(str(t or '').upper(),str(t or '').upper())
def stamp(s):
 try:
  x=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'));return x.astimezone(dt.timezone.utc) if x.tzinfo else None
 except (ValueError,TypeError):return None

def extract_athlete_id(a,item):
 """Extract an ESPN athlete ID from ESPN player-profile links or athlete API references.
 Never confuse injury item.id with athlete ID.
 """
 if not isinstance(a,dict): return ''
 direct=a.get('id')
 if direct is not None and re.fullmatch(r'\d+',str(direct)): return str(direct)
 candidates=[]
 for k in ('$ref','href','url'):
  if isinstance(a.get(k),str): candidates.append(a[k])
 links=a.get('links',[])
 if isinstance(links,list):
  candidates.extend(x.get('href','') for x in links if isinstance(x,dict) and isinstance(x.get('href'),str))
 for value in candidates:
  if not isinstance(value,str): continue
  # ESPN athlete API: /athletes/1234 ; ESPN profile: /nfl/player/_/id/1234
  # Avoid using a generic /id/ match outside known athlete/player URL paths.
  m=re.search(r'/athletes/(\d+)(?:[/?#]|$)',value)
  if m: return m.group(1)
  m=re.search(r'/nfl/player/_/id/(\d+)(?:[/?#]|$)',value)
  if m:return m.group(1)
 return ''

def safe_shape(value):
 """Return key names and types only; never export credentials or raw payload."""
 if isinstance(value,dict):return {str(k):type(v).__name__ for k,v in value.items()}
 return {'type':type(value).__name__}

now=dt.datetime.now(dt.timezone.utc)
with (ROOT/'phase3c3d12_player_game_evidence.csv').open(newline='') as f: players=list(csv.DictReader(f))
audit={'phase':'3C-3D21C','mode':'PREVIEW_ONLY','generated_utc':now.isoformat(),'reference_players':len(players),'supabase_access':'NONE','db_writes':0,'db_deletes':0,'snapshot_approvals':0,'source_fetch_ok':False,'source_parse_ok':False,'proposed_inserts':0,'rls_verified':False,'constraints_verified':False,'warnings':[]}
feed={}; source_hash=''
try:
 req=urllib.request.Request(URL,headers={'User-Agent':'NFL-Parlay-ReadOnly-Audit/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=35) as r: raw=r.read(10000000)
 source_hash=hashlib.sha256(raw).hexdigest(); data=json.loads(raw)
 groups=data.get('injuries',[]) if isinstance(data,dict) else []
 if not isinstance(groups,list):raise ValueError('Unexpected ESPN injuries group structure')
 audit['source_team_groups']=len(groups)
 audit['source_raw_injury_items']=sum(len(g.get('injuries',[])) for g in groups if isinstance(g,dict) and isinstance(g.get('injuries',[]),list))
 audit['sample_group_shape']=safe_shape(groups[0]) if groups else {}
 sample_item=next((i for g in groups if isinstance(g,dict) for i in g.get('injuries',[]) if isinstance(i,dict)),{})
 audit['sample_item_shape']=safe_shape(sample_item)
 audit['sample_athlete_shape']=safe_shape(sample_item.get('athlete'))
 audit['sample_athlete_ref_present']=bool(isinstance(sample_item.get('athlete'),dict) and sample_item['athlete'].get('$ref'))
 for group in groups:
  if not isinstance(group,dict):continue
  groupteam=TEAMS.get(str(group.get('id','')),'')
  for item in group.get('injuries',[]):
   if not isinstance(item,dict):continue
   a=item.get('athlete') or {}
   if not isinstance(a,dict):continue
   t=a.get('team') or {}; t=t if isinstance(t,dict) else {}
   pid=extract_athlete_id(a,item)
   team=normalize(t.get('abbreviation') or groupteam)
   status=item.get('status') or ''
   if isinstance(status,dict):status=status.get('name') or status.get('displayName') or ''
   if pid:feed.setdefault(pid,[]).append({'team':team,'name':a.get('displayName') or a.get('fullName') or '', 'status':str(status),'date':str(item.get('date') or ''),'group_team':groupteam})
 audit['sample_link_path_shapes']=[re.sub(r'\d+','<id>',__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(l.get('href','')).path)[:140] for l in (sample_item.get('athlete') or {}).get('links',[])[:4] if isinstance(l,dict) and isinstance(l.get('href'),str)]
 audit['source_fetch_ok']=True; audit['source_sha256']=source_hash; audit['source_records']=sum(map(len,feed.values()))
 audit['source_distinct_ids']=len(feed)
 audit['source_id_parse_rate']=round(audit['source_records']/audit['source_raw_injury_items'],3) if audit['source_raw_injury_items'] else 0
 audit['source_parse_ok']=audit['source_records']>0
 if not audit['source_parse_ok']:audit['warnings'].append('PARSER_EMPTY: HTTP success but zero parsed athlete IDs; inspect safe shape diagnostics; do not interpret as zero injuries')
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
 reason=('FEED_UNAVAILABLE' if not audit['source_fetch_ok'] else 'PARSER_EMPTY' if not audit['source_parse_ok'] else 'NO_MATCH' if not matches else 'TEAM_CONFLICT' if conflict else 'MULTIPLE_STATUSES' if len(statuses)>1 else 'MISSING_TIMESTAMP' if age is None else 'STALE_OR_FUTURE' if age<0 or age>48 else 'FRESH_EVIDENCE_REVIEW')
 rows.append({'season':'','week':'','game_id':p['game_id'],'player_id':pid,'player_name':p['player'],'team':team,'designation':statuses[0] if len(statuses)==1 else '', 'practice_status':'','source':'ESPN_UNOFFICIAL_PREVIEW','source_updated_at':recent.isoformat() if recent else '', 'fetched_at':now.isoformat(), 'review_reason':reason,'proposed_insert':False,'official_inactive_verified':False})
with (OUT/'initial_load_preview_NOT_FOR_IMPORT.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
audit['review_reasons']=dict(collections.Counter(r['review_reason'] for r in rows))
audit['matched_reference_players']=sum(r['review_reason'] not in ('NO_MATCH','PARSER_EMPTY','FEED_UNAVAILABLE') for r in rows)
audit['reference_unique_keys']=len({(r['game_id'],r['player_id']) for r in rows})
audit['parser_validation']='PASS' if audit['source_parse_ok'] else 'FAIL'
audit['warnings']+=['season/week intentionally blank: must derive from authoritative schedule and verify before writes','ESPN is not an official inactive list; even fresh Active is not clearance','Manual SQL audit required to verify RLS, constraints and grants','No insert proposal authorized until database security and source freshness validated']
(OUT/'audit.json').write_text(json.dumps(audit,indent=2))
print(json.dumps(audit,indent=2))
if len(players)!=41:raise SystemExit('Reference count changed; review required')
if not audit['source_fetch_ok']:raise SystemExit('Source fetch failed; see artifact')
if not audit['source_parse_ok']:raise SystemExit('ESPN parser extracted zero records; see artifact. No changes made.')
