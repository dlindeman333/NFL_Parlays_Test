#!/usr/bin/env python3
"""Read-only game-level prediction storage plan. No database mutation code exists."""
import argparse, collections, datetime as dt, hashlib, json, os, pathlib, urllib.parse, urllib.request

UTC=dt.timezone.utc
METRICS={'pass_attempts','pass_yards','rush_attempts','rush_yards','targets','receptions','rec_yards'}

def parse_time(s):
    try:
        d=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return d.astimezone(UTC) if d.tzinfo else None
    except (ValueError,TypeError):return None

def group_candidates(candidates,manifest,now,existing_keys,minimum_lead_minutes=15):
    groups=collections.defaultdict(list);reject=collections.Counter();seen=set()
    season=manifest.get('season');week=manifest.get('week')
    for c in candidates:
        try:
            gid=str(c['game_id']);pid=str(c['espn_id']);metric=c['metric'];kick=parse_time(c['kickoff_at']);
            key=f'{season}/{week}/{gid}/{pid}/{metric}'
            baseline=float(c['baseline'])
            if c.get('logical_key')!=key or metric not in METRICS or not (0<baseline<10000):raise ValueError('invalid_candidate')
            if c.get('source_sha256')!=manifest.get('source_sha256'):raise ValueError('source_hash_mismatch')
            if key in seen:raise ValueError('duplicate_logical_key')
            seen.add(key)
            if kick is None or kick<=now+dt.timedelta(minutes=minimum_lead_minutes):raise ValueError('kickoff_gate')
            groups[(season,week,gid,c['kickoff_at'])].append({'pick_key':key,'espn_id':pid,'metric':metric,'baseline':baseline})
        except (ValueError,TypeError,KeyError) as exc:reject[str(exc) or 'invalid_candidate']+=1
    plans=[]
    for (s,w,gid,kick),picks in sorted(groups.items()):
        status='SKIP_EXISTING' if (s,w,gid) in existing_keys else 'DRY_RUN_ONLY'
        plans.append({'season':s,'week':w,'game_id':gid,'kickoff_at':kick,'candidate_picks':len(picks),
            'status':status,'pick_keys_sha256':hashlib.sha256('\n'.join(sorted(p['pick_key'] for p in picks)).encode()).hexdigest()})
    return plans,dict(reject)

def fetch_existing():
    from phase3_test_boundary import validate
    validate(os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("SUPABASE_URL", ""))
    url=os.environ['SUPABASE_URL'].rstrip('/')
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.supabase.co') or parsed.path or parsed.query:raise ValueError('invalid_supabase_url')
    results=[];offset=0
    while True:
        path=f'/rest/v1/nfl_prediction_snapshots?select=season,week,game_id&order=season.asc,week.asc,game_id.asc&limit=1000&offset={offset}'
        req=urllib.request.Request(url+path,headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'},method='GET')
        with urllib.request.urlopen(req,timeout=30) as response:page=json.load(response)
        if not isinstance(page,list):raise ValueError('invalid_supabase_response')
        results.extend(page)
        if len(page)<1000:break
        offset+=len(page)
        if offset>100000:raise ValueError('pagination_limit')
    return {(int(r['season']),int(r['week']),str(r['game_id'])) for r in results}

def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',default='phase3d37h-output');p.add_argument('--output-dir',default='phase3d37j-output');a=p.parse_args()
    src=pathlib.Path(a.input_dir);out=pathlib.Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((src/'manifest.json').read_text());candidates=json.loads((src/'candidates.json').read_text());raw=(src/'source.csv').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest.get('source_sha256'):raise ValueError('source_fingerprint_mismatch')
    if len(candidates)!=manifest.get('candidate_metrics'):raise ValueError('candidate_count_mismatch')
    now=dt.datetime.now(UTC);existing=fetch_existing();plans,rejections=group_candidates(candidates,manifest,now,existing)
    # Do not mistake existing historical data for proof that the new pick schema is compatible.
    report={'phase':'3D37J','mode':'READ_ONLY_STORAGE_DRY_RUN','audited_at_utc':now.isoformat(),
      'season':manifest.get('season'),'week':manifest.get('week'),'source_sha256':manifest.get('source_sha256'),
      'candidate_metrics_input':len(candidates),'game_plans':plans,'candidate_rejections':rejections,
      'existing_snapshot_keys_count':len(existing),'new_game_plans':sum(x['status']=='DRY_RUN_ONLY' for x in plans),
      'existing_game_skips':sum(x['status']=='SKIP_EXISTING' for x in plans),
      'readiness':'BLOCKED_PENDING_PICK_JSON_COMPATIBILITY_AND_EXPLICIT_WRITE_APPROVAL',
      'write_operations':0,'snapshot_rows_inserted':0,'grades_inserted':0,
      'limitations':['No POST/PATCH/DELETE or upsert exists in this worker',
        'No picks JSON compatibility asserted: requires inspection of existing snapshots',
        'Candidate baseline values are not sportsbook picks or validated predictions',
        'A service-role credential bypasses RLS; any future writer needs separate review',
        'Forward-only kickoff gate is necessary but not sufficient for publication-time provenance',
        'Existing snapshots are immutable and must never be overwritten']}
    (out/'storage_dry_run.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'new_game_plans':report['new_game_plans'],'existing_game_skips':report['existing_game_skips'],'rejected':sum(rejections.values()),'writes':0,'readiness':report['readiness']}))
if __name__=='__main__':main()
