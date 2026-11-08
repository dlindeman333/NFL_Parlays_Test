#!/usr/bin/env python3
"""Read-only ESPN injury parser audit. No Supabase access, no approvals."""
import collections,csv,datetime,json,pathlib,re,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d8-report');OUT.mkdir(exist_ok=True)
URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'
TEAM_IDS={'1':'ATL','2':'BUF','3':'CHI','4':'CIN','5':'CLE','6':'DAL','7':'DEN','8':'DET','9':'GB','10':'TEN','11':'IND','12':'KC','13':'LV','14':'LA','15':'MIA','16':'MIN','17':'NE','18':'NO','19':'NYG','20':'NYJ','21':'PHI','22':'ARI','23':'PIT','24':'LAC','25':'SF','26':'SEA','27':'TB','28':'WAS','29':'CAR','30':'JAC','33':'BAL','34':'HOU'}
def norm(s):
 s=re.sub(r'\b(jr|sr|ii|iii|iv|v)\b','',str(s or '').lower());return re.sub(r'[^a-z0-9]','',s)
def code(s):return {'JAX':'JAC','LAR':'LA','WSH':'WAS','OAK':'LV','SD':'LAC','STL':'LA'}.get(str(s or '').upper(),str(s or '').upper())
def athlete_id(a):
 if a.get('id'):return str(a['id']),'athlete.id'
 for link in a.get('links',[]) or []:
  href=link.get('href','') if isinstance(link,dict) else ''
  for pat in (r'/id/(\d+)(?:/|$|\?)',r'/athletes/(\d+)(?:/|$|\?)'):
   m=re.search(pat,href)
   if m:return m.group(1),'athlete.links'
 return '',''
def parse(data):
 rows=[]; groups=data.get('injuries',[]) if isinstance(data,dict) else []
 for g in groups if isinstance(groups,list) else []:
  if not isinstance(g,dict):continue
  gid=str(g.get('id','')); parent=TEAM_IDS.get(gid,'')
  for item in g.get('injuries',[]) or []:
   if not isinstance(item,dict):continue
   a=item.get('athlete') or {};a=a if isinstance(a,dict) else {}
   at=a.get('team') or {};at=at if isinstance(at,dict) else {}
   tc=code(at.get('abbreviation',''))
   team=tc or parent
   pid,method=athlete_id(a)
   rows.append({'team':team,'team_source':'athlete.team.abbreviation' if tc else ('parent_group_id' if parent else 'UNKNOWN'),'group_id':gid,'name':str(a.get('displayName') or a.get('fullName') or ''),'espn_id':pid,'id_source':method,'raw_status':str(item.get('status') or ''),'date':str(item.get('date') or ''),'injury_record_id':str(item.get('id') or ''),'team_conflict':bool(tc and parent and tc!=parent)})
 return rows

def main():
 mapping=json.loads((ROOT/'phase3c3d8_player_ids.json').read_text())
 report={'mode':'READ_ONLY_PARSER_CORRECTION','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':URL,'source_error':None,'model_players':len(mapping),'snapshot_approved':0,'game_day_active_verified':0,'limitations':['ESPN API undocumented; completeness unverified','No record does not imply healthy or active','ESPN Active is not game-day active','Historical player identity mapping must be revalidated','No official game-day inactive list','No database access or writes']}
 rows=[];results=[]
 try:
  req=urllib.request.Request(URL,headers={'User-Agent':'NFL-Parlay-ReadOnly-Audit/1.0','Accept':'application/json'})
  with urllib.request.urlopen(req,timeout=50) as f:data=json.load(f)
  rows=parse(data)
  report.update({'source_timestamp':data.get('timestamp'),'source_status':data.get('status'),'team_groups':len(data.get('injuries',[])),'injury_records':len(rows),'team_extracted':sum(bool(r['team']) for r in rows),'id_extracted':sum(bool(r['espn_id']) for r in rows),'id_source_counts':dict(collections.Counter(r['id_source'] or 'NONE' for r in rows)),'team_source_counts':dict(collections.Counter(r['team_source'] for r in rows)),'team_conflicts':sum(r['team_conflict'] for r in rows),'status_counts':dict(collections.Counter(r['raw_status'] for r in rows)),'unrecognized_parent_groups':sorted({r['group_id'] for r in rows if r['team_source']=='UNKNOWN'})})
  for p in mapping:
   pid=str(p['espn_id']);team=code(p['team']);name=norm(p['player'])
   idmatches=[r for r in rows if r['espn_id']==pid]
   namematches=[r for r in rows if norm(r['name'])==name and r['team']==team]
   selected=idmatches or namematches
   ambiguous=len({(r['team'],r['espn_id'],norm(r['name'])) for r in selected})>1
   mismatch=bool(idmatches and any(r['team']!=team for r in idmatches))
   result='ID_MATCH' if idmatches and not mismatch and not ambiguous else 'NAME_TEAM_MATCH' if namematches and not ambiguous else 'CONFLICT' if mismatch or ambiguous else 'NO_INJURY_RECORD'
   results.append({'player':p['player'],'expected_team':team,'expected_espn_id':pid,'match_result':result,'id_match_records':len(idmatches),'name_team_match_records':len(namematches),'observed_teams':' | '.join(sorted({r['team'] for r in selected})),'observed_statuses':' | '.join(sorted({r['raw_status'] for r in selected})),'source_dates':' | '.join(sorted({r['date'] for r in selected})),'availability':'UNVERIFIED','game_day_active_verified':False,'snapshot_approved':False})
  report['match_result_counts']=dict(collections.Counter(r['match_result'] for r in results))
  report['unique_model_players_with_record']=sum(r['match_result'] in ('ID_MATCH','NAME_TEAM_MATCH') for r in results)
 except Exception as e:report['source_error']=f'{type(e).__name__}: {e}'
 if rows:
  with (OUT/'injury_records.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 if results:
  with (OUT/'players.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 (OUT/'audit.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2));print('READ ONLY. No approvals or database writes.')
if __name__=='__main__':main()
