#!/usr/bin/env python3
"""Capture read-only, reproducible acquisition evidence. Does not establish historical source availability."""
import argparse, csv, hashlib, io, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from phase3d36c_supabase_stats import fetch_latest
from phase3d37d_readiness import valid_weekly_row, choose_columns
from phase3d37c_crosswalk import utc

UTC=timezone.utc

def sha256(blob): return hashlib.sha256(blob).hexdigest()

def classify(csv_text, season, week, captured_at):
    reader=csv.DictReader(io.StringIO(csv_text,newline=''))
    headers=reader.fieldnames or []
    required={'player_id','season','week','team','game_status','game_date'}
    missing=sorted(required-set(headers))
    counts={'total_rows':0,'completed_prior_week_rows':0,'excluded_rows':0}
    reasons={}
    if missing: return {'missing_columns':missing,'counts':counts,'exclusions':reasons,'raw_metrics':choose_columns(set(headers))}
    for r in reader:
        counts['total_rows']+=1
        reason=valid_weekly_row(r,season,week,captured_at)
        if reason:
            counts['excluded_rows']+=1;reasons[reason]=reasons.get(reason,0)+1
        else: counts['completed_prior_week_rows']+=1
    return {'missing_columns':[],'counts':counts,'exclusions':reasons,'raw_metrics':choose_columns(set(headers))}

def build_manifest(export, csv_bytes, season, week, start, end, assessment):
    generated=utc(export.get('generated_at'))
    warnings=[]
    if not generated: warnings.append('export_generated_at_missing_or_invalid')
    elif generated>end: warnings.append('export_timestamp_after_capture')
    if assessment['missing_columns']: warnings.append('required_columns_missing')
    if not assessment['counts']['completed_prior_week_rows']: warnings.append('no_eligible_completed_week_rows')
    warnings += ['per_row_publication_or_ingestion_time_unverified',
                 'upstream_source_version_unverified',
                 'game_date_semantics_unverified',
                 'historical_roster_membership_unverified']
    return {
      'phase':'3D37E','mode':'READ_ONLY','season':season,'week':week,
      'capture_started_utc':start.isoformat(),'capture_completed_utc':end.isoformat(),
      'source':'Supabase nfl_stat_exports (GET only)',
      'export_generated_at_utc':generated.isoformat() if generated else None,
      'source_record_count_declared':export.get('record_count'),
      'raw_csv_filename':'source_stats.csv','raw_csv_sha256':sha256(csv_bytes),
      'raw_csv_size_bytes':len(csv_bytes),'schema_columns':list(csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig'))).fieldnames or []),
      'assessment':assessment,'warnings':warnings,
      'capture_integrity_verified':True,'historical_point_in_time_verified':False,
      'readiness':'BLOCKED_FOR_AUTOMATED_SNAPSHOTS',
      'database_writes':0,'prediction_snapshots_created':0,'grades_created':0,
      'artifact_retention_note':'GitHub Actions artifacts are retained per repository settings; this is a timestamped capture, not a cryptographically signed or independently immutable upstream source.'}

def capture(season,week,outdir,fetch_fn=fetch_latest,clock=lambda:datetime.now(UTC)):
    start=clock()
    export=fetch_fn(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'],season)
    if not export or not isinstance(export.get('csv_text'),str):raise ValueError('Missing source export')
    blob=export['csv_text'].encode('utf-8')
    if not blob or len(blob)>12_000_000:raise ValueError('Invalid export size')
    end=clock()
    if end<start:raise ValueError('Clock moved backwards')
    assessment=classify(export['csv_text'],season,week,end)
    manifest=build_manifest(export,blob,season,week,start,end,assessment)
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'source_stats.csv').write_bytes(blob)
    (outdir/'capture_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest

def verify(directory):
    m=json.loads((directory/'capture_manifest.json').read_text(encoding='utf-8'))
    blob=(directory/m['raw_csv_filename']).read_bytes()
    return len(blob)==m['raw_csv_size_bytes'] and sha256(blob)==m['raw_csv_sha256']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int,default=10)
    p.add_argument('--output-dir',default='phase3d37e-evidence');p.add_argument('--verify',action='store_true')
    args=p.parse_args();out=Path(args.output_dir)
    if args.verify:
        ok=verify(out);print(json.dumps({'sha256_verified':ok}));return 0 if ok else 1
    if not 2000<=args.season<=2100 or not 1<=args.week<=18:raise ValueError('Invalid season/week')
    m=capture(args.season,args.week,out)
    print(json.dumps({'captured':True,'sha256_verified':verify(out),'rows':m['assessment']['counts']['total_rows'],
                      'historical_point_in_time_verified':False,'writes':0}))
    return 0
if __name__=='__main__':
    try: sys.exit(main())
    except Exception as e:
        print(json.dumps({'status':'failed','error_type':type(e).__name__}),file=sys.stderr);sys.exit(1)
