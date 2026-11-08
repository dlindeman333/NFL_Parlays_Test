#!/usr/bin/env python3
"""Read-only ESPN injury JSON shape and identity matching diagnostic. No database access."""
import collections,csv,datetime,json,pathlib,re,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d7-report');OUT.mkdir(exist_ok=True)
URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'
def norm(s):
 s=re.sub(r'\b(jr|sr|ii|iii|iv|v)\b','',str(s or '').lower());return re.sub('[^a-z0-9]','',s)
def team(s):return {'JAX':'JAC','LAR':'LA','WSH':'WAS'}.get(str(s or '').upper(),str(s or '').upper())
def val(obj,*keys):
 for k in keys:
  if isinstance(obj,dict) and obj.get(k) not in (None,''):return obj[k]
 return None
def string(x):
 if isinstance(x,dict):return str(val(x,'name','description','displayName','abbreviation','type') or '')
 return str(x or '')
def walk(obj,depth=0):
 if depth>5:return
 if isinstance(obj,dict):
  yield obj
  for k,v in obj.items():
   if isinstance(v,(dict,list)):yield from walk(v,depth+1)
 elif isinstance(obj,list):
  for v in obj:yield from walk(v,depth+1)
def main():
 mapping=json.loads((ROOT/'phase3c3d7_player_ids.json').read_text())
 report={'mode':'READ_ONLY_INJURY_SCHEMA_DIAGNOSTIC','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':URL,'identity_mapping_source':'Phase 3D5 audit, historical snapshot of ESPN roster IDs; revalidation required before any production use','model_players':len(mapping),'source_error':None,'snapshot_approved':0,'game_day_active_verified':0}
 rows=[];samples=[]
 try:
  req=urllib.request.Request(URL,headers={'User-Agent':'NFL-Parlay-ReadOnly-Diagnostics/1.0','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=50) as f:data=json.load(f)
  report['top_level_keys']=list(data) if isinstance(data,dict) else []
  report['top_level_types']={k:type(v).__name__ for k,v in data.items()} if isinstance(data,dict) else {}
  groups=data.get('injuries',[]) if isinstance(data,dict) else []
  report['group_count']=len(groups) if isinstance(groups,list) else 0
  report['first_group_keys']=list(groups[0]) if groups and isinstance(groups[0],dict) else []
  report['pagination_fields']={k:data[k] for k in ('count','total','limit','page','offset','next','pageCount') if k in data and isinstance(data[k],(str,int,float,bool,type(None)))} if isinstance(data,dict) else {}
  for g in groups if isinstance(groups,list) else []:
   if not isinstance(g,dict):continue
   t=g.get('team') or {};tcode=string(val(t,'abbreviation','shortDisplayName')) if isinstance(t,dict) else ''
   for item in g.get('injuries',[]) or []:
    if not isinstance(item,dict):continue
    a=item.get('athlete') or {};a=a if isinstance(a,dict) else {}
    rows.append({'team':team(tcode),'name':string(val(a,'displayName','fullName','name') or val(item,'name')),'id':str(val(a,'id','uid') or ''),'status':string(val(item,'status','type')),'date':string(val(item,'date','lastUpdated') or val(g,'date')),'item_keys':list(item),'athlete_keys':list(a)})
    if len(samples)<4:samples.append({'group_keys':list(g),'injury_keys':list(item),'athlete_keys':list(a),'sample_values':{'team':tcode,'name':string(val(a,'displayName','fullName','name')),'id':str(val(a,'id','uid') or ''),'status':string(val(item,'status','type')),'date':string(val(item,'date','lastUpdated'))}})
  report['parsed_rows']=len(rows)
  report['nonempty_fields']={k:sum(bool(r[k]) for r in rows) for k in ('team','name','id','status','date')}
  report['item_key_frequencies']=dict(collections.Counter(k for r in rows for k in r['item_keys']).most_common(35))
  report['athlete_key_frequencies']=dict(collections.Counter(k for r in rows for k in r['athlete_keys']).most_common(35))
  report['status_counts']=dict(collections.Counter(r['status'] for r in rows).most_common(25))
  report['team_counts']=dict(collections.Counter(r['team'] for r in rows).most_common())
  report['sample_structure']=samples
  # Search nested records for any player IDs, even if the original extraction path was wrong.
  id_hits=collections.Counter();id_samples=[]
  for g in groups if isinstance(groups,list) else []:
   for node in walk(g):
    if 'id' in node and isinstance(node['id'],(str,int)):
     id_hits[str(node['id'])]+=1
     if len(id_samples)<5:id_samples.append({'keys':list(node)[:20],'id':str(node['id'])})
  report['nested_id_occurrences']=sum(id_hits.values());report['nested_id_examples']=id_samples
  report['nested_id_model_overlap']=sum(1 for p in mapping if str(p['espn_id']) in id_hits)
  results=[]
  for p in mapping:
   byid=[r for r in rows if r['id'] and r['id']==str(p['espn_id'])]
   byname=[r for r in rows if norm(r['name'])==norm(p['player']) and r['team']==team(p['team'])]
   results.append({'player':p['player'],'team':p['team'],'espn_id':p['espn_id'],'parsed_id_matches':len(byid),'name_team_matches':len(byname),'nested_id_seen':str(p['espn_id']) in id_hits,'raw_statuses':' | '.join(sorted(set(r['status'] for r in byid or byname)))[:250],'source_dates':' | '.join(sorted(set(r['date'] for r in byid or byname)))[:250],'game_day_active_verified':False,'snapshot_approved':False})
  report['parsed_id_matched_players']=sum(r['parsed_id_matches']>0 for r in results)
  report['name_team_matched_players']=sum(r['name_team_matches']>0 for r in results)
  report['limitations']=['ESPN endpoint is undocumented and may change','A 200 HTTP response does not establish complete injury report coverage','Absence of injury record does not mean healthy or active','No official game-day inactives are checked','Mapping comes from an earlier audit and may become stale','No Supabase access or writes; no snapshot eligibility granted']
  with (OUT/'players.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 except Exception as e:
  report['source_error']=f'{type(e).__name__}: {e}'
  report['limitations']=['Source failed; all injury statuses remain UNKNOWN','No Supabase access or writes']
 (OUT/'audit.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k not in ('sample_structure','team_counts','item_key_frequencies','athlete_key_frequencies')},indent=2))
 print('READ ONLY. No player cleared, no snapshot approved.')
if __name__=='__main__':main()
