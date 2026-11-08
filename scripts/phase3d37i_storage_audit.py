#!/usr/bin/env python3
"""Read-only Supabase REST audit; no mutation capability."""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

TABLES = ('nfl_prediction_snapshots', 'nfl_prediction_grades', 'nfl_user_prediction_tracking')

def get_json(url, key, path):
    req = urllib.request.Request(url.rstrip('/') + '/rest/v1/' + path, headers={
        'apikey': key, 'Authorization': 'Bearer ' + key,
        'Accept': 'application/json', 'Prefer': 'count=exact'}, method='GET')
    with urllib.request.urlopen(req, timeout=35) as response:
        data = json.load(response)
        count_range = response.headers.get('Content-Range', '')
    if not isinstance(data, list): raise ValueError('Unexpected REST response')
    return data, count_range

def audit_table(url, key, name):
    # Query only 30 rows, solely to discover visible columns. Do not export record values.
    rows, count_range = get_json(url, key, urllib.parse.quote(name) + '?select=*&limit=30')
    return {'table': name, 'observed_columns': sorted(set().union(*(r.keys() for r in rows))),
            'sample_rows_inspected': len(rows), 'content_range': count_range,
            'note': 'REST cannot establish RLS/policies, indexes, constraints, or full schema.'}

def audit(url, key):
    report = {'phase':'3D37I', 'mode':'READ_ONLY_SCHEMA_AUDIT',
              'audited_at_utc':datetime.now(timezone.utc).isoformat(),
              'tables':[], 'write_operations':0, 'readiness':'BLOCKED_PENDING_SQL_POLICY_AND_SCHEMA_REVIEW',
              'limitations':['REST GET cannot prove RLS enforcement or policy definitions.',
                             'REST sample cannot prove a unique index or existing logical-key coverage.',
                             'No rows are exported and no prediction writes are attempted.',
                             'A service-role key bypasses RLS; never expose it to client-side code.',
                             'Do not overwrite or backfill historical predictions.']}
    for name in TABLES:
        try: report['tables'].append(audit_table(url,key,name))
        except Exception as exc:
            report['tables'].append({'table':name, 'error_type':type(exc).__name__,
                                     'status':'UNAVAILABLE_OR_QUERY_FAILED'})
    return report

def main():
    url=os.environ.get('SUPABASE_URL',''); key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')
    if not url.startswith('https://') or not key:
        print('Required Supabase GitHub secrets missing',file=sys.stderr);return 2
    report=audit(url,key)
    out=Path('phase3d37i_report');out.mkdir(exist_ok=True)
    (out/'storage_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Read-only audit complete; table status:', [(t['table'],t.get('sample_rows_inspected','unavailable')) for t in report['tables']])
    print('Writes: 0; readiness:',report['readiness'])
    return 0
if __name__=='__main__':sys.exit(main())
