#!/usr/bin/env python3
"""Read-only compatibility audit; never prints raw historical picks."""
import collections, datetime as dt, json, os, pathlib, urllib.parse, urllib.request

BASE_FIELDS={'season','week','game_id','away_team','home_team','kickoff_at','created_at','model_version','picks'}

def describe_picks(value):
    if isinstance(value,list):
        kind='array'; items=value
    elif isinstance(value,dict):
        kind='object'; items=list(value.values())
    else:
        return {'container':type(value).__name__,'length':0,'item_types':{},'object_field_sets':[]}
    types=collections.Counter(type(x).__name__ for x in items)
    fields=collections.Counter(tuple(sorted(x.keys())) for x in items if isinstance(x,dict))
    return {'container':kind,'length':len(items),'item_types':dict(types),
            'object_field_sets':[{'fields':list(k),'count':v} for k,v in fields.most_common(12)]}

def analyze(rows):
    results=[]; totals=collections.Counter()
    for row in rows:
        if not isinstance(row,dict) or not BASE_FIELDS.issubset(row):raise ValueError('unexpected_snapshot_schema')
        shape=describe_picks(row['picks'])
        totals[shape['container']]+=1
        results.append({'season':row['season'],'week':row['week'],'game_id':str(row['game_id']),
            'model_version':row['model_version'],'pick_shape':shape,
            'kickoff_before_creation':_before(row['kickoff_at'],row['created_at'])})
    return {'snapshot_count':len(results),'pick_container_counts':dict(totals),
            'snapshot_shapes':results}

def _before(kick,created):
    try:
        a=dt.datetime.fromisoformat(str(kick).replace('Z','+00:00'))
        b=dt.datetime.fromisoformat(str(created).replace('Z','+00:00'))
        return a<=b
    except (ValueError,TypeError):return None

def fetch():
    url=os.environ['SUPABASE_URL'].rstrip('/');key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.supabase.co') or parsed.path or parsed.query:raise ValueError('invalid_supabase_url')
    rows=[];offset=0
    while True:
        path='/rest/v1/nfl_prediction_snapshots?select=season,week,game_id,away_team,home_team,kickoff_at,created_at,model_version,picks&order=season.asc,week.asc,game_id.asc&limit=500&offset='+str(offset)
        req=urllib.request.Request(url+path,headers={'apikey':key,'Authorization':'Bearer '+key,'Accept':'application/json'},method='GET')
        with urllib.request.urlopen(req,timeout=30) as response:page=json.load(response)
        if not isinstance(page,list):raise ValueError('invalid_response')
        rows.extend(page)
        if len(page)<500:break
        offset+=len(page)
        if offset>100000:raise ValueError('pagination_limit')
    return rows

def main():
    rows=fetch();audit=analyze(rows)
    audit.update({'phase':'3D37K','mode':'READ_ONLY_PICK_JSON_COMPATIBILITY',
        'audited_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'readiness':'BLOCKED_PENDING_CONTRACT_MAPPING_AND_EXPLICIT_WRITE_APPROVAL',
        'write_operations':0,
        'limitations':['Historical pick values intentionally omitted; only structural field names and types are reported',
                       'No new pick serialization or application compatibility is asserted',
                       'This audit does not verify RLS or service-role grants',
                       'No existing snapshots or grades are modified']})
    out=pathlib.Path('phase3d37k-output');out.mkdir(exist_ok=True)
    (out/'pick_compatibility_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps({'snapshot_count':audit['snapshot_count'],'containers':audit['pick_container_counts'],'writes':0,'readiness':audit['readiness']}))
if __name__=='__main__':main()
