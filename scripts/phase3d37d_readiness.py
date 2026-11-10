#!/usr/bin/env python3
"""Phase 3D37D: read-only point-in-time readiness audit. No prediction snapshots."""
import argparse,csv,io,json,os,hashlib
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path
from phase3d37c_crosswalk import (download_registry,REGISTRY_URL,build_crosswalk,normalized_gsis,
 canonical_team,utc)
from phase3d36c_supabase_stats import fetch_latest
from phase3d36b_stats_candidates import number
from phase3d37b_roster_match import BASE,fetch,teams,athletes,games,verify

RAW_METRICS={
 'pass_yards':('pass_yards','passing_yards'),
 'rush_yards':('rush_yards','rushing_yards'),
 'rec_yards':('rec_yards','receiving_yards'),
 'receptions':('receptions',),
 'pass_attempts':('pass_attempts','passing_attempts'),
 'rush_attempts':('rush_attempts','rushing_attempts'),
 'targets':('targets','receiving_targets'),
}
def choose_columns(headers):
 return {k:next((h for h in names if h in headers),None) for k,names in RAW_METRICS.items()}
def valid_weekly_row(r,season,week,cutoff):
 if str(r.get('season'))!=str(season):return 'wrong_season'
 w=number(r.get('week'))
 if w is None or w!=int(w) or not 1<=w<week:return 'not_prior_week'
 if str(r.get('is_future','')).strip().lower() in ('true','yes','1'):return 'future_row'
 if str(r.get('game_status','')).strip().lower() not in ('final','completed','complete','post'):return 'not_final'
 # A week number alone cannot prove the row's event preceded cutoff.
 date=utc(r.get('game_date'))
 if not date:return 'missing_game_date'
 if date>=cutoff:return 'game_date_not_before_kickoff'
 return None
def recompute(history,cols):
 out={}
 for metric,col in cols.items():
  if not col:continue
  vals=[number(r.get(col)) for r in history]
  if any(v is None or v<0 for v in vals):continue
  if len(vals)<3:continue
  recent=sum(vals[-3:])/3
  season_avg=sum(vals)/len(vals)
  out[metric]={'baseline':round(.6*recent+.4*season_avg,1),'last3':round(recent,2),
    'season':round(season_avg,2),'games':len(vals),'opponent_adjusted':False,'injury_adjusted':False}
 return out
def audit(rows,export_time,season,week,now,crosswalk,matches,abbr):
 report={'source_rows':len(rows),'source_headers':sorted(rows[0].keys()) if rows else [],
         'status_counts':{},'matched_player_count':0,'recomputed_player_count':0,
         'recomputed_metric_count':0,'sample_previews':[],
         'point_in_time_verified':False,'snapshots_created':0,'grades_created':0,'database_writes':0}
 counts=Counter()
 cols=choose_columns(set(rows[0]) if rows else set())
 report['raw_metric_columns']=cols
 exp=utc(export_time)
 by_espn={m['player_id']:m for m in matches if m['status']=='matched'}
 grouped=defaultdict(list)
 for r in rows:
  gsis=normalized_gsis(r.get('player_id'));espn=crosswalk.get(gsis) if gsis else None
  if not espn:counts['unmapped_id']+=1;continue
  m=by_espn.get(espn)
  if not m:counts['no_verified_upcoming_game']+=1;continue
  if canonical_team(r.get('team'))!=canonical_team(abbr.get(m['team_id'])):
   counts['team_mismatch']+=1;continue
  kickoff=utc(m.get('kickoff_at'))
  if not kickoff or kickoff<=now:counts['game_already_started']+=1;continue
  if not exp or exp>now or exp>=kickoff:counts['export_after_kickoff']+=1;continue
  reason=valid_weekly_row(r,season,week,kickoff)
  if reason:counts[reason]+=1;continue
  grouped[espn].append((int(number(r['week'])),r,m))
  counts['eligible_historical_rows']+=1
 for espn,items in grouped.items():
  counts['matched_players']+=1
  # Require unique completed week records; no double counting.
  by_week=defaultdict(list)
  for w,r,m in items:by_week[w].append(r)
  if any(len(v)!=1 for v in by_week.values()):
   counts['duplicate_week_conflict_players']+=1;continue
  history=[by_week[w][0] for w in sorted(by_week)]
  projections=recompute(history,cols)
  if not projections:
   counts['insufficient_raw_history_or_metrics']+=1;continue
  counts['recomputed_players']+=1
  counts['recomputed_metrics']+=len(projections)
  if len(report['sample_previews'])<10:
   m=items[0][2]
   report['sample_previews'].append({'espn_id':espn,'game_id':m['game_id'],
      'kickoff_at':m['kickoff_at'],'opponent':canonical_team(abbr.get(m['opponent_team_id'])),
      'source_weeks':sorted(by_week),'metrics':projections})
 report['status_counts']=dict(counts)
 report['matched_player_count']=counts['matched_players']
 report['recomputed_player_count']=counts['recomputed_players']
 report['recomputed_metric_count']=counts['recomputed_metrics']
 # Export timestamp alone cannot establish that derived historical rows are immutable or reproducible.
 report['point_in_time_verified']=False
 report['readiness']='BLOCKED_FOR_AUTOMATED_SNAPSHOTS'
 report['limitations']=[
  'game_date is required but its semantics and final-stat publication time are not independently verified',
  'No per-row ingestion timestamps or immutable source version are verified',
  'Defensive rank and injury adjustments are intentionally disabled',
  'Current roster is not a historical roster; report is a present-time preview only']
 return report
def run(season,week):
 now=datetime.now(timezone.utc)
 result={'phase':'3D37D','mode':'READ_ONLY','season':season,'week':week,'run_at_utc':now.isoformat(),
         'status':'error','database_writes':0,'snapshots_created':0,'grades_created':0}
 try:
  registry=download_registry(REGISTRY_URL);crosswalk,registry_info=build_crosswalk(registry)
  team_list=teams(fetch(BASE+'/teams?limit=50'))
  if len(team_list)!=32:raise ValueError('incomplete_teams')
  abbr={str(t['id']):str(t.get('abbreviation','')).upper() for t in team_list}
  roster=defaultdict(list)
  for t in team_list:
   for a in athletes(fetch(BASE+f"/teams/{t['id']}/roster")):
    pid=str(a.get('id','')).strip()
    if pid:roster[pid].append({'team_id':str(t['id'])})
  schedule=games(fetch(BASE+f'/scoreboard?dates={season}&week={week}&seasontype=2&limit=1000'))
  if not schedule:raise ValueError('missing_schedule')
  matches=verify(roster,schedule,now)
  export=fetch_latest(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],season)
  if not export or not export.get('csv_text'):raise ValueError('missing_export')
  reader=csv.DictReader(io.StringIO(export['csv_text'],newline=''))
  rows=list(reader)
  if not {'player_id','season','week','team','game_status','game_date'}.issubset(reader.fieldnames or []):
   result.update(status='blocked',missing_required_columns=sorted({'player_id','season','week','team','game_status','game_date'}-set(reader.fieldnames or [])),
    available_headers=reader.fieldnames or [],readiness='BLOCKED_FOR_AUTOMATED_SNAPSHOTS')
   return result
  result.update(audit(rows,export.get('generated_at'),season,week,now,crosswalk,matches,abbr))
  result.update(status='ok',export_generated_at=export.get('generated_at'),
    source_csv_sha256=hashlib.sha256(export['csv_text'].encode('utf-8')).hexdigest(),
    roster_players=len(roster),games_found=len(schedule),**registry_info)
 except Exception as exc:
  result['error_type']=type(exc).__name__
  result['error_message']=str(exc)[:140] if isinstance(exc,ValueError) else 'Source retrieval or parsing failed'
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int,default=10)
 p.add_argument('--output',default='phase3d37d_readiness_report.json');a=p.parse_args()
 if not 1<=a.week<=18:raise SystemExit('Invalid week')
 r=run(a.season,a.week);Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:r.get(k) for k in ('status','readiness','matched_player_count','recomputed_player_count','status_counts','missing_required_columns','error_type')}))
 if r['status']=='error':raise SystemExit(1)
