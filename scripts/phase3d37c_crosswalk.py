#!/usr/bin/env python3
"""Read-only GSIS->ESPN identity join; never writes or creates predictions."""
import argparse,csv,io,json,os,re,time,random
from urllib.error import HTTPError, URLError
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from phase3d36c_supabase_stats import fetch_latest,MAX_CSV_BYTES
from phase3d36b_stats_candidates import candidate,number
from phase3d37b_roster_match import BASE,fetch,teams,athletes,games,verify,parse_dt

# nflverse player registry release. Pin/verify source and archive a copy before production use.
REGISTRY_URL='https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
MAX_REGISTRY_BYTES=30_000_000

def normalized_gsis(value):
    v=str(value or '').strip()
    return v if re.fullmatch(r'00-\d{7}',v) else None

def normalized_espn(value):
    v=str(value or '').strip()
    if re.fullmatch(r'\d+(?:\.0)?',v):return str(int(float(v)))
    return None

def build_crosswalk(rows):
    """Return only one-to-one mappings. Ambiguous mappings are excluded."""
    forward=defaultdict(set); reverse=defaultdict(set)
    for r in rows:
        gsis=normalized_gsis(r.get('gsis_id')); espn=normalized_espn(r.get('espn_id'))
        if gsis and espn:forward[gsis].add(espn);reverse[espn].add(gsis)
    unique={g:next(iter(ids)) for g,ids in forward.items() if len(ids)==1 and len(reverse[next(iter(ids))])==1}
    return unique, {'registry_unique_pairs':len(unique),'registry_ambiguous_gsis':sum(len(v)>1 for v in forward.values()),
                    'registry_ambiguous_espn':sum(len(v)>1 for v in reverse.values())}

def download_registry(url):
    """Retry transient upstream failures; never silently use unverified/stale data."""
    if url != REGISTRY_URL:raise ValueError('unapproved_registry_url')
    retryable={429,500,502,503,504}
    max_attempts=5
    for attempt in range(max_attempts):
        try:
            req=Request(url,headers={'User-Agent':'NFLParlayReadOnlyCrosswalk/1.0','Accept':'text/csv'})
            with urlopen(req,timeout=45) as response:
                raw=response.read(MAX_REGISTRY_BYTES+1)
            if len(raw)>MAX_REGISTRY_BYTES:raise ValueError('registry_too_large')
            reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
            if not {'gsis_id','espn_id'}.issubset(reader.fieldnames or []):raise ValueError('registry_missing_id_columns')
            return list(reader)
        except (HTTPError,URLError,TimeoutError) as exc:
            code=getattr(exc,'code',None)
            if isinstance(exc,HTTPError) and code not in retryable:raise
            if attempt==max_attempts-1:raise RuntimeError('player_registry_unavailable_after_5_attempts') from exc
            delay=min(2**attempt*3,24)+random.uniform(0,1)
            print(f'Player registry transient download failure (HTTP {code or "network"}); retry {attempt+2}/{max_attempts} in {delay:.1f}s',flush=True)
            time.sleep(delay)

def utc(value):
    try:return parse_dt(str(value)).astimezone(timezone.utc) if value else None
    except (ValueError,TypeError,AttributeError):return None

TEAM_ALIASES = {'LA':'LAR','STL':'LAR','OAK':'LV','SD':'LAC','JAC':'JAX','WSH':'WAS'}
def canonical_team(value):
    v=str(value or '').strip().upper()
    return TEAM_ALIASES.get(v,v)

def assess(rows,crosswalk,matches,abbr,season,week,export_time,now):
    by_espn={m['player_id']:m for m in matches if m['status']=='matched'}
    all_espn={m['player_id'] for m in matches}
    counts=Counter();samples=defaultdict(list); accepted={}
    exp=utc(export_time)
    for row in rows:
        c,reason=candidate(row,season)
        if reason:counts[reason]+=1;continue
        counts['eligible_stat_rows']+=1
        gsis=normalized_gsis(c['player_id']);espn=crosswalk.get(gsis)
        m=by_espn.get(espn) if espn else None
        if not gsis: reason='invalid_gsis_format'
        elif not espn:reason='gsis_not_in_crosswalk'
        elif espn not in all_espn:reason='espn_not_in_current_roster'
        elif not m:reason='roster_has_no_upcoming_game'
        elif canonical_team(row.get('team'))!=canonical_team(abbr.get(m['team_id'])):reason='team_mismatch'
        elif not utc(m['kickoff_at']) or utc(m['kickoff_at'])<=now:reason='game_started'
        elif not exp or exp>now or exp>=utc(m['kickoff_at']):reason='export_not_point_in_time'
        elif number(row.get('week')) is None or number(row.get('week'))>=week:reason='source_week_not_prior'
        elif utc(row.get('game_date')) and utc(row.get('game_date'))>=utc(m['kickoff_at']):reason='historical_date_not_prior'
        elif str(row.get('game_status','')).strip().lower() not in ('final','completed','complete','post'):reason='unverified_completed_game'
        else:reason='accepted'
        counts[reason]+=1
        if reason!='accepted':
            if len(samples[reason])<3:samples[reason].append({'gsis_id':gsis,'espn_id':espn,'stats_team':row.get('team'),
                 'roster_team':abbr.get(m['team_id']) if m else None,'historical_row_next_opponent':row.get('next_opponent'),
                 'verified_upcoming_opponent':abbr.get(m['opponent_team_id']) if m else None})
            continue
        source_week=number(row.get('week'))
        if espn not in accepted or source_week>accepted[espn][0]:
            accepted[espn]=(source_week,{'gsis_id':gsis,'espn_id':espn,'name':c['name'],
                'team':canonical_team(abbr[m['team_id']]),'opponent':canonical_team(abbr[m['opponent_team_id']]),
                'game_id':m['game_id'],'kickoff_at':m['kickoff_at'],'projections':c['projections']})
    return {'stage_counts':dict(counts),'diagnostic_samples':dict(samples),'matched_projection_players':len(accepted),
            'sample_projections':[v[1] for v in list(accepted.values())[:15]], 'deduplication':'highest eligible completed source week per ESPN player ID', 'opponent_logic':'Historical row next_opponent is not compared with verified upcoming schedule opponent', 'projection_warning':'Existing rolling averages not independently recomputed; preview only, not authenticated point-in-time predictions'}

def run(season,week):
    now=datetime.now(timezone.utc)
    report={'phase':'3D37C-crosswalk','mode':'READ_ONLY','season':season,'week':week,'run_at_utc':now.isoformat(),
        'status':'error','database_writes':0,'snapshots_created':0,'grades_created':0,
        'warning':'Current rosters and exported rolling averages do not prove historical point-in-time eligibility; preview only, not authentic saved predictions.'}
    try:
        registry=download_registry(REGISTRY_URL)
        crosswalk,metrics=build_crosswalk(registry)
        if not crosswalk:raise ValueError('empty_crosswalk')
        team_list=teams(fetch(BASE+'/teams?limit=50'))
        if len(team_list)!=32:raise ValueError('incomplete_team_list')
        abbr={str(t['id']):str(t.get('abbreviation','')).upper() for t in team_list}
        roster=defaultdict(list)
        for t in team_list:
            for a in athletes(fetch(BASE+f"/teams/{t['id']}/roster")):
                pid=normalized_espn(a.get('id'))
                if pid:roster[pid].append({'team_id':str(t['id'])})
        schedule=games(fetch(BASE+f'/scoreboard?dates={season}&week={week}&seasontype=2&limit=1000'))
        if not schedule:raise ValueError('empty_schedule')
        matches=verify(roster,schedule,now)
        export=fetch_latest(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],season)
        if not export or not export.get('csv_text'):raise ValueError('missing_stats_export')
        raw=export['csv_text']
        if len(raw.encode('utf-8'))>MAX_CSV_BYTES:raise ValueError('csv_too_large')
        reader=csv.DictReader(io.StringIO(raw,newline=''))
        needed={'season','week','player_id','name','team','next_opponent','games_played_to_date','game_status'}
        if not needed.issubset(reader.fieldnames or []):raise ValueError('missing_stats_columns')
        rows=list(reader)
        results=assess(rows,crosswalk,matches,abbr,season,week,export.get('generated_at'),now)
        report.update(status='ok',registry_source=REGISTRY_URL,registry_rows=len(registry),**metrics,
            roster_players=len(roster),games_found=len(schedule),stats_rows=len(rows),
            export_generated_at=export.get('generated_at'),**results)
    except Exception as exc:report['error_type']=type(exc).__name__;report['error_message']=str(exc)[:160] if isinstance(exc,ValueError) else 'Source retrieval or parsing failed'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int,default=10);p.add_argument('--output',default='phase3d37c_crosswalk_report.json');a=p.parse_args()
    if not 1<=a.week<=18:raise SystemExit('Invalid week')
    r=run(a.season,a.week);Path(a.output).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:r.get(k) for k in ('status','registry_unique_pairs','matched_projection_players','stage_counts','database_writes','error_type')}))
    if r['status']!='ok':raise SystemExit(1)
