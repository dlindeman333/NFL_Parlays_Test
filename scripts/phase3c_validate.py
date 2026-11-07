#!/usr/bin/env python3
"""Phase 3C-1: read-only eligibility audit, NOT prediction generation."""
import csv, io, json, os, sys, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SEASON = 2026
TZ = ZoneInfo('America/New_York')
REQUIRED = {'season','week','game_status','game_date','game_time','player_id','team','opponent_team','home_away','is_future'}

def fetch():
    url = os.environ.get('SUPABASE_URL','').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
    if not url.startswith('https://') or not key:
        raise ValueError('Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY GitHub secret')
    query=urllib.parse.urlencode({'select':'season,generated_at,record_count,csv_text','season':'eq.2026','limit':'1'})
    req=urllib.request.Request(f'{url}/rest/v1/nfl_stat_exports?{query}',headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=40) as resp:
        data=json.load(resp)
    if len(data)!=1 or not data[0].get('csv_text'):
        raise ValueError('Expected exactly one nonempty 2026 export')
    return data[0]

def parse_kickoff(date,time):
    if not date or not time or date.lower() in {'nan','nat','none'}:
        return None,'missing date/time'
    try:
        # Date and time from exporter are schedule-local, not timezone-qualified.
        d=datetime.strptime(date[:10],'%Y-%m-%d').date()
        t=time.strip().upper().replace(' ET','').replace(' EST','').replace(' EDT','')
        formats=('%H:%M','%H:%M:%S','%I:%M %p','%I:%M%p')
        clock=None
        for fmt in formats:
            try: clock=datetime.strptime(t,fmt).time();break
            except ValueError: pass
        if clock is None: return None,'unrecognized time format'
        local=datetime.combine(d,clock,tzinfo=TZ)
        # Reject nonexistent or ambiguous wall times; don't guess a kickoff.
        utc=local.astimezone(timezone.utc)
        if utc.astimezone(TZ).replace(tzinfo=None)!=local.replace(tzinfo=None):
            return None,'nonexistent local time'
        if local.replace(fold=1).utcoffset()!=local.replace(fold=0).utcoffset():
            return None,'ambiguous local time'
        return utc,None
    except ValueError:
        return None,'invalid date/time'

def main():
    row=fetch()
    raw=row['csv_text']; reader=csv.DictReader(io.StringIO(raw))
    fields=set(reader.fieldnames or [])
    missing=REQUIRED-fields
    if missing: raise ValueError('Missing required CSV columns: '+', '.join(sorted(missing)))
    records=list(reader)
    if not records: raise ValueError('Empty CSV')
    if row.get('record_count') is not None and int(row['record_count'])!=len(records):
        raise ValueError('Export record_count does not match CSV row count')
    if any(r['season'].strip()!='2026' for r in records): raise ValueError('Unexpected season in export')
    now=datetime.now(timezone.utc)
    bygame=defaultdict(list); historical=defaultdict(list)
    for r in records:
        try: week=int(r['week'])
        except ValueError: raise ValueError('Invalid week in CSV')
        if not 1<=week<=18: raise ValueError('Out-of-range week')
        status=r['game_status'].strip().upper()
        if status not in ('SCHEDULED','COMPLETED'): raise ValueError('Invalid game status')
        if status=='COMPLETED': historical[r['player_id']].append(r)
        if status=='SCHEDULED':
            team=r['team'].strip();opp=r['opponent_team'].strip();venue=r['home_away'].strip().upper()
            if venue not in ('HOME','AWAY') or not team or not opp or team==opp: continue
            home,away=(team,opp) if venue=='HOME' else (opp,team)
            bygame[(week,away,home)].append(r)
    games=[]
    for (week,away,home), players in sorted(bygame.items()):
        dates={(p['game_date'].strip(),p['game_time'].strip()) for p in players}
        problems=[]
        if len(dates)!=1: problems.append('inconsistent schedule timestamps')
        date,time=next(iter(dates))
        kickoff,reason=parse_kickoff(date,time)
        if reason: problems.append(reason)
        if kickoff and kickoff<=now: problems.append('kickoff passed')
        if kickoff and kickoff>now+timedelta(days=14): problems.append('more than 14 days away')
        if len({p['player_id'] for p in players})!=len(players): problems.append('duplicate player rows')
        if not any(p['team']==home for p in players) or not any(p['team']==away for p in players): problems.append('one team missing future player rows')
        with_history=sum(bool(historical.get(p['player_id'])) for p in players)
        if with_history==0: problems.append('no historical player rows')
        games.append({'week':week,'away':away,'home':home,'kickoff_utc':kickoff.isoformat() if kickoff else None,
                      'future_player_rows':len(players),'players_with_history':with_history,
                      'status':'ELIGIBLE_FOR_MODEL_REVIEW' if not problems else 'BLOCKED', 'reasons':problems})
    summary={'mode':'READ_ONLY_VALIDATION','season':SEASON,'checked_at_utc':now.isoformat(),
             'export_generated_at':row.get('generated_at'),'csv_rows':len(records),'csv_columns':len(fields),
             'scheduled_games_found':len(games),'eligible_games':sum(g['status']=='ELIGIBLE_FOR_MODEL_REVIEW' for g in games),
             'blocked_games':sum(g['status']=='BLOCKED' for g in games),
             'important':'Eligibility is not proof of model parity, freshness, roster availability or snapshot safety. No predictions generated and no database writes.'}
    report={'summary':summary,'games':games}
    os.makedirs('phase3c-report',exist_ok=True)
    with open('phase3c-report/validation.json','w',encoding='utf-8') as f: json.dump(report,f,indent=2)
    print(json.dumps(summary,indent=2))
    for g in games:
        if g['status']=='ELIGIBLE_FOR_MODEL_REVIEW':print('ELIGIBLE',g['week'],g['away'],'@',g['home'],g['kickoff_utc'])
        else: print('BLOCKED',g['week'],g['away'],'@',g['home'],'; '.join(g['reasons']))
    print('READ-ONLY COMPLETE. No Supabase write performed.')
    # A report with no eligible games is still a successful audit.

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(f'VALIDATION FAILED: {e}',file=sys.stderr);sys.exit(1)
