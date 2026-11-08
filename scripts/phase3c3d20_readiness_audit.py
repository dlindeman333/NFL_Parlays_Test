#!/usr/bin/env python3
"""Phase 3C-3D20: read-only schema and official inactive evidence audit.
No writes, player clearance, or prediction approvals. GitHub workflow manual only.
"""
import csv,datetime as dt,json,os,pathlib,re,urllib.parse,urllib.request,html
from collections import Counter
from html.parser import HTMLParser
BASE=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d20-report');OUT.mkdir(exist_ok=True)
NOW=dt.datetime.now(dt.timezone.utc)
HEAD={'User-Agent':'NFL-Parlay-Phase3D20-ReadOnly/1.0','Accept':'application/json, text/html'}
def fetch(url,extra=None,limit=4000000):
 req=urllib.request.Request(url,headers={**HEAD,**(extra or {})},method='GET')
 with urllib.request.urlopen(req,timeout=30) as r:
  raw=r.read(limit+1); status=r.status; final=r.geturl()
 if len(raw)>limit: raise ValueError('response size limit exceeded')
 return raw,status,final
def parse_json(raw): return json.loads(raw.decode('utf-8'))
def error(e): return type(e).__name__+': '+str(e)[:160]
def utc(s):
 try:
  d=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'))
  return d.astimezone(dt.timezone.utc) if d.tzinfo else None
 except (TypeError,ValueError): return None
class Text(HTMLParser):
 def __init__(self): super().__init__();self.text=[];self.links=[];self.href=None;self.in_a=False;self.skip=0
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag in ('script','style','nav','footer'):self.skip+=1
  if tag=='a':self.in_a=True;self.href=attrs.get('href')
 def handle_endtag(self,tag):
  if tag in ('script','style','nav','footer') and self.skip:self.skip-=1
  if tag=='a':self.in_a=False;self.href=None
 def handle_data(self,data):
  if self.skip:return
  t=' '.join(html.unescape(data).split())
  if t:
   self.text.append(t)
   if self.in_a and self.href:self.links.append((t,self.href))
def main():
 with (BASE/'phase3c3d12_player_game_evidence.csv').open(newline='',encoding='utf-8') as f: players=list(csv.DictReader(f))
 audit={'phase':'3C-3D20','mode':'READ_ONLY','generated_utc':NOW.isoformat(),'reference_players':len(players),'db_writes':0,'db_deletes':0,'snapshot_approvals':0,'official_game_day_clearances':0,'supabase':{},'espn':{},'nfl_official':{},'limitations':['NFL.com article discovery is not official inactive-list completeness validation','ESPN injury statuses are not official game-day inactives','Empty database is not authorization to insert rows','No status changes or player approvals','Manual workflow only; no scheduled writes']}
 url=os.getenv('SUPABASE_URL','').rstrip('/');key=os.getenv('SUPABASE_SERVICE_ROLE_KEY','')
 parsed=urllib.parse.urlsplit(url)
 if not url or not key: audit['supabase']['state']='NOT_CONFIGURED'
 elif parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.supabase.co') or parsed.username or parsed.password: audit['supabase']['state']='INVALID_URL'
 else:
  headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'}
  endpoint=url+'/rest/v1/nfl_player_injuries'
  try:
   raw,status,_=fetch(endpoint+'?select=*&limit=1',headers)
   rows=parse_json(raw)
   audit['supabase']['state']='READ_OK' if isinstance(rows,list) else 'UNEXPECTED_RESPONSE'
   audit['supabase']['sample_row_keys']=sorted(rows[0].keys()) if isinstance(rows,list) and rows and isinstance(rows[0],dict) else []
   # Exact count via HEAD intentionally avoided: GET + Prefer count=exact is read-only.
   raw,status,_=fetch(endpoint+'?select=*&limit=0',{**headers,'Prefer':'count=exact'})
   audit['supabase']['count_probe']='GET_OK'
  except Exception as e: audit['supabase']['state']='READ_ERROR';audit['supabase']['error']=error(e)
  # PostgREST OpenAPI is metadata only; service role required, no data modifications.
  try:
   raw,status,_=fetch(url+'/rest/v1/',{**headers,'Accept':'application/openapi+json'})
   spec=parse_json(raw); definition=(spec.get('definitions') or {}).get('nfl_player_injuries') or {}
   props=definition.get('properties') or {}
   audit['supabase']['openapi_available']=True
   audit['supabase']['columns']=[{'name':k,'type':v.get('type'),'format':v.get('format'),'description':str(v.get('description',''))[:150]} for k,v in props.items()]
   audit['supabase']['required']=definition.get('required',[])
   audit['supabase']['primary_keys']=[k for k,v in props.items() if 'primary key' in str(v.get('description','')).lower()]
   audit['supabase']['openapi_warning']='OpenAPI does not prove RLS policy or unique constraints; verify separately before writes'
  except Exception as e: audit['supabase']['openapi_available']=False;audit['supabase']['openapi_error']=error(e)
  # Explicit read-only information_schema probe is not available through PostgREST by default.
  audit['supabase']['rls_verified']=False
  audit['supabase']['constraint_verification']='NOT_AVAILABLE_FROM_POSTGREST'
 try:
  raw,status,final=fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&limit=300')
  data=parse_json(raw);events=data.get('events',[])
  audit['espn']={'state':'READ_OK','events_retrieved':len(events),'source':final}
  game_rows=[]
  for ev in events:
   comps=(ev.get('competitions') or [{}]);comp=comps[0] if comps else {}
   teams=[c.get('team',{}).get('abbreviation','') for c in comp.get('competitors',[])]
   game_rows.append({'game_id':str(ev.get('id','')),'kickoff_utc':str(ev.get('date','')),'teams':' / '.join(teams),'status':str((ev.get('status') or {}).get('type',{}).get('name',''))})
 except Exception as e: audit['espn']={'state':'FETCH_ERROR','error':error(e)};game_rows=[]
 with (OUT/'espn_games.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=['game_id','kickoff_utc','teams','status']);w.writeheader();w.writerows(game_rows)
 # Official NFL inactive landing page only. Do not infer team completeness or player status.
 try:
  raw,status,final=fetch('https://www.nfl.com/inactives/')
  page=Text();page.feed(raw.decode('utf-8',errors='replace'))
  candidates=[];seen=set()
  for title,href in page.links:
   absolute=urllib.parse.urljoin(final,href);p=urllib.parse.urlsplit(absolute)
   if p.hostname not in ('www.nfl.com','nfl.com') or '/news/' not in p.path:continue
   if not ('inactive' in title.lower() or 'inactive' in p.path.lower()):continue
   canonical='https://www.nfl.com'+p.path
   if canonical not in seen:seen.add(canonical);candidates.append({'title':title,'url':canonical})
  audit['nfl_official']={'state':'INDEX_READ_OK','index_status':status,'candidate_articles':len(candidates),'verified_complete_reports':0,'verified_players':0,'warning':'Article links do not certify report date, matchup, or completeness'}
 except Exception as e:
  candidates=[];audit['nfl_official']={'state':'INDEX_ERROR','error':error(e),'verified_complete_reports':0,'verified_players':0}
 with (OUT/'official_article_candidates.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=['title','url']);w.writeheader();w.writerows(candidates)
 ref_games=sorted(set(p['game_id'] for p in players));audit['reference_games']=len(ref_games)
 audit['safety_gate']={'schema_confirmed':bool(audit['supabase'].get('columns')),'rls_confirmed':False,'official_inactives_complete':False,'eligible_for_writes':False,'eligible_for_snapshots':False}
 with (OUT/'audit.json').open('w') as f:json.dump(audit,f,indent=2)
 with (OUT/'player_status_review.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=['player','team','espn_player_id','game_id','kickoff_utc','official_status','reason']);w.writeheader()
  for p in players:w.writerow({**{k:p.get(k,'') for k in ('player','team','espn_player_id','game_id','kickoff_utc')},'official_status':'UNKNOWN','reason':'Official game-specific complete inactive report not verified'})
 print(json.dumps(audit,indent=2))
 if len(players)!=41:raise SystemExit('Unexpected reference-player count')
if __name__=='__main__':main()
