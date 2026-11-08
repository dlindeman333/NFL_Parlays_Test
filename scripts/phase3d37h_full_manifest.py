#!/usr/bin/env python3
"""Full-population, forward-only READ-ONLY prediction manifest. No database writes."""
import argparse,csv,hashlib,io,json,os
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from phase3d36c_supabase_stats import fetch_latest
from phase3d37b_roster_match import BASE,fetch,teams,athletes,games,verify
from phase3d37c_crosswalk import download_registry,REGISTRY_URL,build_crosswalk,normalized_gsis,canonical_team,utc
from phase3d37d_readiness import choose_columns,valid_weekly_row,recompute
from phase3d37f_pregame import current_week,freshness
from phase3d37g_forward_gate import metric_allowed,stable_key


def build_manifest(rows, crosswalk, matches, abbr, positions, schedule, season, week, now, export_time, source_hash, lead_minutes=30):
    counts=Counter(); entries=[]; grouped=defaultdict(list)
    by_player={m['player_id']:m for m in matches if m['status']=='matched'}
    schedule_by_id={str(g['game_id']):g for g in schedule}
    cols=choose_columns(set(rows[0]) if rows else set())
    stale=freshness(export_time,now,12)
    if stale: counts['source_freshness_blocker']+=1
    for r in rows:
        pid=crosswalk.get(normalized_gsis(r.get('player_id')))
        if not pid:counts['unmapped_id']+=1;continue
        m=by_player.get(pid)
        if not m:counts['no_verified_upcoming_game']+=1;continue
        if canonical_team(r.get('team'))!=canonical_team(abbr.get(m['team_id'])):
            counts['team_mismatch']+=1;continue
        kickoff=utc(m.get('kickoff_at'))
        game=schedule_by_id.get(str(m['game_id']))
        if not kickoff or not game or kickoff!=utc(game.get('kickoff_at')) or kickoff<=now+timedelta(minutes=lead_minutes):
            counts['kickoff_not_safely_ahead']+=1;continue
        if str(game.get('status','')).lower() not in ('status_scheduled','scheduled','pre'):
            counts['game_not_scheduled']+=1;continue
        if not utc(export_time) or utc(export_time)>=kickoff or utc(export_time)>now:
            counts['invalid_export_time']+=1;continue
        reason=valid_weekly_row(r,season,week,kickoff)
        if reason:counts[reason]+=1;continue
        grouped[pid].append((int(r['week']),r,m))
        counts['eligible_history_rows']+=1
    seen=set()
    for pid,history in sorted(grouped.items()):
        by_week=defaultdict(list)
        for w,r,m in history:by_week[w].append(r)
        if any(len(v)!=1 for v in by_week.values()):counts['duplicate_week_player_blocked']+=1;continue
        metrics=recompute([by_week[w][0] for w in sorted(by_week)],cols)
        if not metrics:counts['insufficient_history']+=1;continue
        pos=positions.get(pid)
        if not pos:counts['unverified_position']+=1;continue
        m=history[0][2]
        for metric,data in sorted(metrics.items()):
            baseline=data['baseline']
            if not metric_allowed(pos,metric,baseline):counts['inapplicable_metric']+=1;continue
            key=stable_key(season,week,str(m['game_id']),pid,metric)
            if key in seen:counts['duplicate_identity']+=1;continue
            seen.add(key)
            entries.append({'logical_key':key,'espn_id':pid,'position':pos,'game_id':str(m['game_id']),
                'kickoff_at':m['kickoff_at'],'metric':metric,'baseline':baseline,
                'history_weeks':sorted(by_week),'source_sha256':source_hash})
            counts['eligible_metric_previews']+=1
    return entries,dict(counts),cols,stale


def main():
    p=argparse.ArgumentParser();p.add_argument('--season',type=int);p.add_argument('--week',type=int)
    p.add_argument('--output-dir',default='phase3d37h-output');a=p.parse_args()
    now=datetime.now(timezone.utc)
    if a.season is None or a.week is None:
        s,w=current_week(fetch(BASE+'/scoreboard?limit=100'))
        season=a.season or s;week=a.week or w
    else:season,week=a.season,a.week
    if not 2000<=season<=2100 or not 1<=week<=18:raise ValueError('invalid_season_week')
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    source=fetch_latest(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],season)
    if not source or not source.get('csv_text'):raise ValueError('missing_source_export')
    raw=source['csv_text'].encode('utf-8');sha=hashlib.sha256(raw).hexdigest()
    reader=csv.DictReader(io.StringIO(source['csv_text'],newline=''))
    rows=list(reader)
    required={'player_id','season','week','team','game_status','game_date'}
    if not required.issubset(reader.fieldnames or []):raise ValueError('missing_required_headers: '+','.join(sorted(required-set(reader.fieldnames or []))))
    crosswalk,registry_info=build_crosswalk(download_registry(REGISTRY_URL))
    team_list=teams(fetch(BASE+'/teams?limit=50'))
    if len(team_list)!=32:raise ValueError('incomplete_team_list')
    abbr={str(t['id']):t.get('abbreviation','') for t in team_list}
    roster=defaultdict(list);positions={}
    for t in team_list:
        tid=str(t['id'])
        for player in athletes(fetch(BASE+f'/teams/{tid}/roster')):
            pid=str(player.get('id','')).strip()
            if not pid:continue
            pos=player.get('position',{})
            pos=pos.get('abbreviation') if isinstance(pos,dict) else None
            roster[pid].append({'team_id':tid,'position':pos})
    for pid,recs in roster.items():
        if len(recs)==1:positions[pid]=recs[0].get('position')
    schedule=games(fetch(BASE+f'/scoreboard?dates={season}&week={week}&seasontype=2&limit=1000'))
    if not schedule:raise ValueError('missing_schedule')
    entries,counts,cols,stale=build_manifest(rows,crosswalk,verify(roster,schedule,now),abbr,positions,schedule,season,week,now,source.get('generated_at'),sha)
    manifest={'phase':'3D37H','mode':'READ_ONLY_FULL_POPULATION_PREVIEW','season':season,'week':week,
        'run_at_utc':now.isoformat(),'source_acquired_at_utc':now.isoformat(),
        'source_generated_at':source.get('generated_at'),'source_sha256':sha,
        'source_record_count':len(rows),'source_byte_count':len(raw),'source_headers':reader.fieldnames,
        'registry':registry_info,'schedule_game_count':len(schedule),'roster_player_count':len(roster),
        'raw_metric_columns':cols,'status_counts':counts,'source_freshness_blocker':stale,
        'candidate_players':len({e['espn_id'] for e in entries}),'candidate_metrics':len(entries),
        'unique_logical_keys':len({e['logical_key'] for e in entries}),
        'readiness':'BLOCKED_FOR_AUTOMATED_SNAPSHOTS',
        'limitations':['Upstream row publication timestamps are not independently verified',
          'Current rosters are not historical rosters','Source capture is immutable only within the retained GitHub Actions artifact',
          'No odds, injury, or defensive matchup adjustments have been validated'],
        'database_writes':0,'snapshots_created':0,'grades_created':0}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (out/'candidates.json').write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
    (out/'source.csv').write_bytes(raw)
    print(json.dumps({'candidate_players':manifest['candidate_players'],'candidate_metrics':len(entries),'readiness':manifest['readiness'],'database_writes':0}))

if __name__=='__main__':main()
