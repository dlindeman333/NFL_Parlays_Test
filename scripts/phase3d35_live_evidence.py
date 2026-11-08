#!/usr/bin/env python3
"""Phase 3D35: read-only live evidence, never authentic predictions or grades."""
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

INJURY_URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'
SCORE_URL='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'
TABLES=('nfl_player_injuries','nfl_prediction_snapshots','nfl_prediction_grades','nfl_automation_runs')

def fetch_json(url, headers=None):
    request=urllib.request.Request(url,headers=headers or {'User-Agent':'NFL-Parlay-ReadOnly-Audit/1.0'},method='GET')
    with urllib.request.urlopen(request,timeout=35) as response:
        return json.load(response)

def validate_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or not re.fullmatch(r'[a-z0-9-]+\.supabase\.co',p.hostname or '') or p.path not in ('','/') or p.query or p.fragment:
        raise ValueError('Invalid Supabase project URL')
    return url.rstrip('/')

def supabase_count(url, secret, table):
    if table not in TABLES: raise ValueError('Unapproved table')
    req=urllib.request.Request(url+'/rest/v1/'+table+'?select=*&limit=0',headers={
        'apikey':secret,'Authorization':'Bearer '+secret,'Prefer':'count=exact','Range':'0-0','Accept':'application/json'},method='HEAD')
    with urllib.request.urlopen(req,timeout=35) as r:
        cr=r.headers.get('Content-Range','')
    if '/' not in cr or not cr.rsplit('/',1)[-1].isdigit():
        raise ValueError('Supabase count unavailable for '+table)
    return int(cr.rsplit('/',1)[-1])

def summarize_injuries(payload):
    if not isinstance(payload,dict):raise ValueError('Invalid ESPN injury response')
    # Feed shape may change; report structure only, never infer player availability.
    return {'top_level_keys':sorted(payload.keys())[:20],
            'injuries_field_type':type(payload.get('injuries')).__name__,
            'team_groups':len(payload.get('injuries',[])) if isinstance(payload.get('injuries'),list) else None,
            'player_status_verified':False}

def summarize_schedule(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('events'),list):raise ValueError('Invalid ESPN scoreboard response')
    events=payload['events']
    return {'events_returned':len(events),'events_with_id_and_kickoff':sum(bool(e.get('id') and e.get('date')) for e in events),
            'event_details_exported':False,'kickoff_independently_verified':False}

def main():
    out=Path('phase3d35_live_evidence_report.json')
    report={'phase':'3D35','mode':'READ_ONLY_LIVE_EVIDENCE','writes_enabled':False,'authentic_predictions_generated':0,
            'grades_calculated':0,'full_league_injury_mapping_completed':False,
            'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'sources':{},'supabase_counts':{},'errors':[]}
    for name,url,fn in [('espn_injuries',INJURY_URL,summarize_injuries),('espn_scoreboard',SCORE_URL,summarize_schedule)]:
        try:report['sources'][name]=fn(fetch_json(url))
        except Exception as exc:report['errors'].append(name+': '+type(exc).__name__)
    try:
        url=validate_url(os.environ['SUPABASE_URL']);secret=os.environ['SUPABASE_SERVICE_ROLE_KEY']
        if not secret:raise ValueError('Missing key')
        for table in TABLES:
            try:report['supabase_counts'][table]=supabase_count(url,secret,table)
            except Exception as exc:report['errors'].append(table+': '+type(exc).__name__)
    except (KeyError,ValueError) as exc:report['errors'].append('supabase_setup: '+type(exc).__name__)
    report['success']=not report['errors']
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'success':report['success'],'counts':report['supabase_counts'],'errors':report['errors']}))
    if not report['success']:raise SystemExit(1)

if __name__=='__main__':main()
