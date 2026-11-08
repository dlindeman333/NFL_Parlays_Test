#!/usr/bin/env python3
"""Phase 3D16: NFL.com official article discovery and conservative parsing DIAGNOSTIC.
No credentials, no database operations, no player availability determinations.
"""
import csv, datetime as dt, hashlib, html, json, os, re, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE='https://www.nfl.com'
INDEX=BASE+'/inactives/'
OUT=Path('phase3c3d16-report')
INPUT=Path('scripts/phase3c3d12_player_game_evidence.csv')
UA='NFLParlayReadOnlyAudit/3D16 (diagnostic; public pages)'

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[];self.blocks=[];self._a=None;self._buffer=[];self._tag=None
        self.skip=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style','noscript'): self.skip+=1
        if tag=='a': self._a={'href':attrs.get('href',''),'text':''}
        if tag in ('h1','h2','h3','h4','li','p','td','th'):
            self._tag=tag;self._buffer=[]
    def handle_data(self,data):
        if self.skip:return
        if self._a is not None:self._a['text']+=data
        if self._tag:self._buffer.append(data)
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript') and self.skip:self.skip-=1
        if tag=='a' and self._a is not None:
            self._a['text']=' '.join(self._a['text'].split())
            self.links.append(self._a);self._a=None
        if tag==self._tag:
            s=' '.join(' '.join(self._buffer).split())
            if s:self.blocks.append({'tag':tag,'text':s[:1000]})
            self._tag=None;self._buffer=[]

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=25) as r:
        data=r.read(2500000);status=r.status;final=r.url
    return data.decode('utf-8','replace'),status,final,hashlib.sha256(data).hexdigest()

def clean_url(href):
    url=urllib.parse.urljoin(BASE,href)
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in ('www.nfl.com','nfl.com'):return None
    return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,'',''))

def is_inactive_article(url):
    path=urllib.parse.urlsplit(url).path.lower()
    return path.startswith('/news/') and 'inactive' in path and 'injury-report' not in path

def extract_article(html_text):
    p=PageParser();p.feed(html_text)
    # This is evidence extraction only; article text alone cannot prove completeness.
    markers=[{'index':i,'tag':b['tag'],'text':b['text']} for i,b in enumerate(p.blocks)
             if re.search(r'(?i)\b(inactives?|not playing|will not play|ruled out)\b',b['text'])]
    contexts=[]
    for m in markers[:50]:
        i=m['index'];contexts.append({'marker':m,'preceding':p.blocks[max(0,i-2):i],
                                      'following':p.blocks[i+1:i+7]})
    return {'title_candidates':[b['text'] for b in p.blocks if b['tag']=='h1'][:5],
            'blocks_count':len(p.blocks),'inactive_contexts':contexts,
            'list_items':[b['text'] for b in p.blocks if b['tag']=='li'][:100],
            'completeness':'UNVERIFIED','player_status':'UNKNOWN'}

def main():
    OUT.mkdir(exist_ok=True)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    with INPUT.open(newline='',encoding='utf-8-sig') as f: players=list(csv.DictReader(f))
    urls=[];errors=[];index_result={}
    try:
        content,status,final,digest=fetch(INDEX)
        p=PageParser();p.feed(content)
        found={}
        for link in p.links:
            u=clean_url(link['href'])
            if u and is_inactive_article(u):found.setdefault(u,link['text'])
        urls=list(found)[:12]
        index_result={'status':status,'final_url':final,'sha256':digest,'candidate_count':len(found),
                      'candidate_articles':[{'url':u,'anchor':found[u]} for u in found]}
    except Exception as e:
        errors.append({'source':INDEX,'error':str(e)})
    articles=[]
    for u in urls:
        try:
            body,status,final,digest=fetch(u)
            result=extract_article(body)
            articles.append({'url':u,'status':status,'final_url':final,'sha256':digest,**result})
        except Exception as e:
            errors.append({'source':u,'error':str(e)})
    report={'phase':'3C-3D16','retrieved_at_utc':now,'source_index':index_result,
            'articles_fetched':len(articles),'articles':articles,'errors':errors,
            'player_reference_count':len(players),
            'unique_player_ids':len({p['espn_player_id'] for p in players}),
            'distinct_games':len({p['game_id'] for p in players}),
            'verified_official_complete_lists':0,'verified_player_inactives':0,
            'snapshot_approvals':0,'database_writes':0,
            'warning':'Diagnostic extraction only: NO official list completeness or player availability certified.'}
    (OUT/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (OUT/'article_index.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['url','status','title','inactive_markers','list_items','completeness'])
        w.writeheader()
        for a in articles:w.writerow({'url':a['url'],'status':a['status'],
            'title':' | '.join(a['title_candidates']), 'inactive_markers':len(a['inactive_contexts']),
            'list_items':len(a['list_items']),'completeness':a['completeness']})
    with (OUT/'players.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['player','team','espn_player_id','game_id','opponent','kickoff_utc','availability','reason'])
        w.writeheader()
        for p in players:w.writerow({k:p.get(k,'') for k in ('player','team','espn_player_id','game_id','opponent','kickoff_utc')}|
            {'availability':'UNKNOWN','reason':'OFFICIAL_GAME_LIST_NOT_VERIFIED'})
    print(json.dumps({k:report[k] for k in ('phase','articles_fetched','player_reference_count','verified_player_inactives','database_writes')},indent=2))
    if errors:print('Source errors recorded in audit.json:',len(errors))

if __name__=='__main__':main()
