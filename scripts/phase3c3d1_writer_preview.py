#!/usr/bin/env python3
"""Phase 3C-3D1: strictly read-only snapshot writer PREVIEW.
No POST/PATCH/PUT/DELETE, no snapshot creation, no authorization to write.
"""
import csv, hashlib, io, json, os, subprocess, sys, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path('phase3c3d1-report')
ALIASES = {'JAX':'JAC','JAC':'JAC','LAR':'LA','LA':'LA','WSH':'WAS','WAS':'WAS'}
MIN_LEAD = timedelta(minutes=60)
MAX_WINDOW = timedelta(days=7)
MAX_EXPORT_AGE = timedelta(hours=72)

def norm(x):
    x = str(x or '').strip().upper()
    return ALIASES.get(x, x)

def utc(s):
    try:
        dt = datetime.fromisoformat(str(s).replace('Z','+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None

def get_json(path):
    base = os.environ['SUPABASE_URL'].rstrip('/')
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    if not base.startswith('https://'):
        raise ValueError('SUPABASE_URL must be https')
    req = urllib.request.Request(base+'/rest/v1/'+path, method='GET', headers={
        'apikey':key, 'Authorization':'Bearer '+key, 'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)

def main():
    OUT.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    report = {'mode':'READ_ONLY_NO_WRITES', 'generated_utc':now.isoformat(),
              'writer_enabled':False, 'existing_snapshot_count':None,
              'groups':[], 'summary':{}, 'limitations':[
                  'No inserts, updates, deletes, upserts, or RPC calls are performed',
                  'Game IDs are NOT inferred from team abbreviations; actual stored game_id convention must be verified',
                  'Candidate roster status, sportsbook lines, live browser equivalence, and injuries are unverified',
                  'Historical snapshots are read but never modified; this preview cannot authorize a write',
                  'An existing season/week/game primary key is only one protection; service_role can modify rows']}
    try:
        result = subprocess.run([sys.executable,'scripts/phase3c2_preview.py'],
                                capture_output=True, text=True, timeout=180, check=False)
        if result.returncode:
            raise RuntimeError('Prediction preview failed: '+result.stderr[-1000:])
        preview = json.loads(Path('phase3c2-report/preview.json').read_text())
        export_at = utc(preview.get('export_generated_at'))
        fresh = export_at is not None and timedelta(0) <= now-export_at <= MAX_EXPORT_AGE
        report['export_generated_at'] = preview.get('export_generated_at')
        report['export_fresh'] = fresh
        report['candidate_count'] = len(preview.get('predictions',[]))
        # Only read key/timestamp/teams metadata. Never download or alter archived picks.
        existing = get_json('nfl_prediction_snapshots?select=season,week,game_id,away_team,home_team,kickoff_at,created_at&season=eq.2026&limit=1000')
        if not isinstance(existing,list) or len(existing)>=1000:
            raise RuntimeError('Existing snapshot query incomplete or at pagination limit; fail closed')
        report['existing_snapshot_count'] = len(existing)
        by_match = defaultdict(list)
        for s in existing:
            by_match[(int(s['week']),norm(s['away_team']),norm(s['home_team']))].append(s)
        grouped = defaultdict(list)
        for p in preview.get('predictions',[]):
            try:
                away,home = [norm(x) for x in p['game'].split(' @ ')]
                grouped[(int(p['week']),away,home,str(p['kickoff_utc']))].append(p)
            except (KeyError,ValueError,TypeError):
                report.setdefault('invalid_candidates',0)
                report['invalid_candidates'] += 1
        for (week,away,home,kickoff_text),items in sorted(grouped.items()):
            reasons=[]
            kickoff = utc(kickoff_text)
            if not fresh: reasons.append('EXPORT_STALE_OR_INVALID')
            if kickoff is None: reasons.append('INVALID_KICKOFF')
            else:
                if kickoff-now <= MIN_LEAD: reasons.append('KICKOFF_TOO_CLOSE_OR_PASSED')
                if kickoff-now > MAX_WINDOW: reasons.append('OUTSIDE_7_DAY_WINDOW')
            matches = by_match.get((week,away,home),[])
            if matches: reasons.append('EXISTING_SNAPSHOT_FOR_MATCHUP_DO_NOT_OVERWRITE')
            if len(matches)>1: reasons.append('MULTIPLE_STORED_GAME_IDS_FOR_MATCHUP')
            # There is no validated independent schedule ID mapping in this stage.
            reasons.append('GAME_ID_MAPPING_NOT_VERIFIED')
            picks=[]
            seen=set()
            for p in items:
                issues=[]
                if p.get('market') not in ('td','ps','ru'): issues.append('UNSUPPORTED_MARKET')
                if int(p.get('historical_games') or 0)<3: issues.append('INSUFFICIENT_HISTORY')
                if norm(p.get('team')) not in (away,home): issues.append('TEAM_NOT_IN_GAME')
                if p.get('market') in ('ps','ru') and not isinstance(p.get('reference_line'),(float,int)):
                    issues.append('MISSING_LINE')
                if not isinstance(p.get('model_over_probability'),(float,int)):
                    issues.append('MISSING_PROBABILITY')
                signature=(norm(p.get('team')),str(p.get('player','')).lower(),p.get('market'),p.get('reference_line'))
                if signature in seen: issues.append('DUPLICATE_PICK')
                seen.add(signature)
                # The existing app's gradeArchived() expects market='player', stat and side.
                market=p.get('market')
                picks.append({'market':'player', 'player_name':p.get('player'),
                              'team':norm(p.get('team')),
                              'stat':{'ps':'passing_yards','ru':'rushing_yards','td':'touchdowns'}.get(market),
                              'side':'o','line':0.5 if market=='td' else p.get('reference_line'),
                              'model_probability':p.get('model_over_probability'),
                              'projection':p.get('projection'),
                              'label':f"{p.get('player')} {'anytime TD' if market=='td' else ('passing yards' if market=='ps' else 'rushing yards')} over {0.5 if market=='td' else p.get('reference_line')}",
                              'preview_issues':issues})
            if not picks: reasons.append('NO_CANDIDATES')
            if all(p['preview_issues'] for p in picks): reasons.append('NO_ELIGIBLE_PICKS')
            # The intended JSON is illustrative, not approved for live insertion.
            report['groups'].append({'season':2026,'week':week,'away_team':away,'home_team':home,
                                     'kickoff_at':kickoff_text,'game_id':None,
                                     'existing_game_ids':[s['game_id'] for s in matches],
                                     'candidate_picks':len(picks),
                                     'eligible_picks':sum(not p['preview_issues'] for p in picks),
                                     'status':'BLOCKED_NO_WRITE', 'blockers':sorted(set(reasons)),
                                     'illustrative_picks':picks})
        report['summary']={'game_groups':len(report['groups']),
                           'would_insert':0, 'blocked_groups':len(report['groups']),
                           'existing_snapshot_count':len(existing),
                           'blocker_counts':dict(Counter(x for g in report['groups'] for x in g['blockers']))}
        report['status']='PREVIEW_COMPLETE_NO_WRITES'
    except Exception as e:
        report['status']='PREVIEW_FAILED_NO_WRITES'
        report['error']=str(e)
    (OUT/'preview.json').write_text(json.dumps(report,indent=2))
    with (OUT/'games.csv').open('w',newline='') as f:
        cols=['season','week','away_team','home_team','kickoff_at','candidate_picks','eligible_picks','status','blockers','existing_game_ids']
        writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
        for g in report['groups']:
            writer.writerow({k:(', '.join(map(str,g[k])) if isinstance(g.get(k),list) else g.get(k)) for k in cols})
    print(json.dumps({k:report.get(k) for k in ('status','export_fresh','candidate_count','summary','error')},indent=2))
    print('READ ONLY: No database writes performed. Live insertion is NOT implemented.')
    return 0 if report['status']=='PREVIEW_COMPLETE_NO_WRITES' else 2

if __name__=='__main__': sys.exit(main())
