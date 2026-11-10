#!/usr/bin/env python3
"""Strict, deterministic offline archived player-prop grading. No DB/network writes."""
import argparse, csv, datetime as dt, hashlib, json, pathlib
from collections import Counter

STATS = {'pass_attempts','pass_completions','pass_yards','pass_tds','pass_interceptions','rush_attempts','rush_yards','rush_tds','targets','receptions','rec_yards','rec_tds','touchdowns'}

def grade_pick(p, rows, expected_game_id=None):
    if p.get('market') != 'player':
        return {'status':'UNAVAILABLE','reason':'Non-player markets require verified final game scores'}
    stat=p.get('stat'); side=p.get('side'); line=p.get('line')
    if stat not in STATS or side not in ('o','u'):
        return {'status':'UNAVAILABLE','reason':'Unsupported stat or side'}
    try:
        threshold=float(line)
        if not (-1e8 < threshold < 1e8): raise ValueError()
    except (ValueError,TypeError):
        return {'status':'UNAVAILABLE','reason':'Missing or invalid saved betting line'}
    name=str(p.get('player_name') or '').strip().casefold(); team=str(p.get('team') or '').strip().upper()
    if not name or not team: return {'status':'UNAVAILABLE','reason':'Missing player/team identity'}
    matches=[r for r in rows if str(r.get('name') or r.get('player') or '').strip().casefold()==name and str(r.get('team') or '').strip().upper()==team and str(r.get('game_status') or '').upper()=='COMPLETED']
    if expected_game_id is not None:
        # Fail closed: game identity must be present on the final statistics row.
        matches=[r for r in matches if str(r.get('game_id') or '').strip()==str(expected_game_id).strip()]
    if len(matches)!=1: return {'status':'UNAVAILABLE','reason':'Missing or ambiguous completed player row for the expected game'}
    row=matches[0]
    try:
        if stat=='touchdowns':
            actual=sum(float(row[s]) for s in ('pass_tds','rush_tds','rec_tds'))
        else: actual=float(row[stat])
        if not (-1e8 < actual < 1e8): raise ValueError()
    except (KeyError,ValueError,TypeError):
        return {'status':'UNAVAILABLE','reason':'Final statistic missing or invalid'}
    if stat=='touchdowns':
        # Archived browser reader uses >= 1 for TD picks regardless of line.
        if threshold != 0.5 or side!='o': return {'status':'UNAVAILABLE','reason':'Unsupported touchdown contract'}
        return {'status':'HIT' if actual>=1 else 'MISS','actual':actual}
    if actual==threshold: return {'status':'PUSH','actual':actual}
    return {'status':'HIT' if ((actual>threshold) if side=='o' else (actual<threshold)) else 'MISS','actual':actual}

def audit(snapshots, stats):
    indexed={}
    for r in stats:
        try: key=(int(r['season']),int(r['week']))
        except (ValueError,KeyError,TypeError): continue
        indexed.setdefault(key,[]).append(r)
    output=[]
    for snap in snapshots:
        season,week=int(snap['season']),int(snap['week'])
        for i,p in enumerate(snap.get('picks') or []):
            result=grade_pick(p,indexed.get((season,week),[]),expected_game_id=snap.get('game_id'))
            output.append({'season':season,'week':week,'game_id':str(snap.get('game_id','')),'pick_index':i,'status':result['status'],'reason':result.get('reason'),'actual':result.get('actual')})
    counts=Counter(r['status'] for r in output)
    return {'mode':'READ_ONLY_OFFLINE_GRADING_PREVIEW','summary':dict(sorted(counts.items())),'total_picks':len(output),'results':output,'database_writes':0,'readiness':'NO_WRITE_APPROVAL'}

def main():
    a=argparse.ArgumentParser();a.add_argument('--snapshots',required=True);a.add_argument('--stats',required=True);a.add_argument('--output',default='grading-preview.json');args=a.parse_args()
    snaps=json.loads(pathlib.Path(args.snapshots).read_text())
    with open(args.stats,newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    report=audit(snaps,rows)
    pathlib.Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'total_picks':report['total_picks'],'summary':report['summary'],'database_writes':0}))
if __name__=='__main__': main()
