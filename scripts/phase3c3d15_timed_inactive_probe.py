#!/usr/bin/env python3
"""Read-only official NFL.com publication probe and ESPN comparison; never certifies availability."""
import csv, json, re, urllib.request, urllib.error, pathlib, datetime, html, hashlib
from html.parser import HTMLParser

ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path('phase3c3d15-report'); OUT.mkdir(exist_ok=True)
NOW=datetime.datetime.now(datetime.timezone.utc)
UA={'User-Agent':'Mozilla/5.0 (compatible; NFLParlayReadOnlyAudit/1.0)','Accept':'text/html,application/json'}

def get(url):
    req=urllib.request.Request(url,headers=UA)
    try:
        with urllib.request.urlopen(req,timeout=25) as resp:
            data=resp.read(3_000_000); return {'ok':True,'status':resp.status,'url':resp.geturl(),'body':data.decode('utf-8','replace'),'bytes':len(data)}
    except Exception as e:return {'ok':False,'error':str(e),'url':url,'body':''}

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.current=dict(attrs).get('href')
    def handle_data(self,data):
        if self.current and data.strip():self.links.append({'href':self.current,'text':data.strip()[:160]})
    def handle_endtag(self,tag):
        if tag=='a':self.current=None

def iso(v):
    try:return datetime.datetime.fromisoformat(v.replace('Z','+00:00'))
    except:return None

with (ROOT/'phase3c3d12_player_game_evidence.csv').open(newline='',encoding='utf-8-sig') as f:players=list(csv.DictReader(f))
if not players or not all(p.get('game_id') and p.get('espn_player_id') and p.get('kickoff_utc') for p in players):raise RuntimeError('Missing required player/game reference data')
games={p['game_id']:p for p in players}
# The official page is probed for publication and possible links, not scraped into authoritative player decisions.
nfl=get('https://www.nfl.com/inactives/')
parser=Links()
if nfl['ok']:
    try:parser.feed(nfl['body'])
    except Exception:pass
candidate_links=[x for x in parser.links if re.search(r'inactiv|week\s*\d+',x['href']+' '+x['text'],re.I)]
# Only retain small samples and metadata, not the full third-party page.
source={'retrieved_at_utc':NOW.isoformat(),'url':nfl['url'],'http_ok':nfl['ok'],'status':nfl.get('status'),'error':nfl.get('error'),'bytes':nfl.get('bytes'), 'sha256':hashlib.sha256(nfl['body'].encode()).hexdigest() if nfl['ok'] else None,'candidate_link_count':len(candidate_links),'candidate_links':candidate_links[:40], 'html_mentions_inactive':bool(re.search(r'inactive',nfl['body'],re.I)) if nfl['ok'] else False,'official_game_report_verified':False,'reason':'HTML/page metadata alone cannot establish complete game-specific official inactive lists'}
(OUT/'nfl_source_probe.json').write_text(json.dumps(source,indent=2))
rows=[]; game_rows=[]
for gid,p in sorted(games.items()):
    kickoff=iso(p['kickoff_utc']); mins=round((kickoff-NOW).total_seconds()/60) if kickoff else None
    window='BEFORE_PUBLICATION_WINDOW' if mins is not None and mins>90 else ('WITHIN_90_MIN_PRE_KICKOFF' if mins is not None and 0<=mins<=90 else ('AFTER_KICKOFF' if mins is not None else 'UNKNOWN'))
    espn=get(f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={gid}')
    keys=[]; inactive_hits=[]
    if espn['ok']:
        try:
            data=json.loads(espn['body']);keys=list(data.keys())
            # Path-level hints only; no player status derived from these.
            def walk(obj,path='',depth=0):
                if depth>7 or len(inactive_hits)>30:return
                if isinstance(obj,dict):
                    for k,v in obj.items():
                        if 'inactiv' in k.lower():inactive_hits.append(path+'.'+k)
                        if isinstance(v,(dict,list)):walk(v,path+'.'+k,depth+1)
                elif isinstance(obj,list):
                    for i,v in enumerate(obj[:15]):walk(v,path+f'[{i}]',depth+1)
            walk(data)
        except Exception as e:espn['error']='JSON parse: '+str(e)
    game_rows.append({'game_id':gid,'kickoff_utc':p['kickoff_utc'],'minutes_to_kickoff':mins,'publication_window':window,'espn_http_ok':espn['ok'],'espn_error':espn.get('error',''),'espn_top_level_keys':','.join(keys),'inactive_field_hints':','.join(inactive_hits),'official_complete_report_verified':False,'decision':'UNKNOWN_SOURCE_NOT_VERIFIED'})
    for player in [x for x in players if x['game_id']==gid]:
        rows.append({'game_id':gid,'team':player['team'],'player':player['player'],'espn_player_id':player['espn_player_id'],'kickoff_utc':player['kickoff_utc'],'publication_window':window,'official_inactive_status':'UNKNOWN','official_report_complete':False,'injury_status':'NOT_EVALUATED_IN_THIS_PROBE','snapshot_approved':False})
for filename,data in [('games.csv',game_rows),('players.csv',rows)]:
    with (OUT/filename).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
summary={'phase':'3C-3D15','generated_at_utc':NOW.isoformat(),'player_rows':len(rows),'distinct_games':len(game_rows),'nfl_com_page_retrieved':nfl['ok'],'nfl_com_candidate_links':len(candidate_links),'espn_summaries_retrieved':sum(x['espn_http_ok'] for x in game_rows),'within_90_minutes':sum(x['publication_window']=='WITHIN_90_MIN_PRE_KICKOFF' for x in game_rows),'official_complete_game_reports_verified':0,'official_player_statuses_verified':0,'snapshots_approved':0,'supabase_writes':0,'limitations':['NFL.com landing page and links are publication hints, not a parsed authenticated game-specific inactive list.','ESPN game summary field names are diagnostic hints, not verified inactive decisions.','No absence-from-list means active inference is permitted.','Run near kickoff to compare publication windows; even then the audit will remain unverified.','Player-game mapping is a static 3D12 reference and may become outdated.']}
(OUT/'audit.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
