"""Offline integrity and data-rehydration rehearsal for a Package 13 JSON export.

Not a Supabase schema/roles/auth restore. Never connects to or modifies Supabase.
"""
import hashlib
import json
import pathlib
import sqlite3
import sys
import tempfile

EXPECTED = ('nfl_parlay_sync','nfl_stat_exports','nfl_prediction_snapshots',
            'nfl_prediction_grades','nfl_user_prediction_tracking',
            'nfl_player_injuries','nfl_automation_runs')

def rehearse(directory):
    root = pathlib.Path(directory)
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('mode') != 'READ_ONLY_LOGICAL_BACKUP':
        raise ValueError('Not a recognized read-only backup')
    if set(manifest.get('tables', {})) != set(EXPECTED):
        raise ValueError('Backup table list mismatch')
    with tempfile.TemporaryDirectory(prefix='nfl-rehearsal-') as temp:
        db = sqlite3.connect(str(pathlib.Path(temp)/'isolated.sqlite3'))
        db.execute('CREATE TABLE restored (source_table TEXT NOT NULL, ordinal INTEGER NOT NULL, row_json TEXT NOT NULL, PRIMARY KEY(source_table,ordinal))')
        counts = {}
        for table in EXPECTED:
            blob = (root/(table+'.json')).read_bytes()
            entry = manifest['tables'][table]
            if len(blob) != entry['bytes'] or hashlib.sha256(blob).hexdigest() != entry['sha256']:
                raise ValueError(f'Backup integrity mismatch: {table}')
            rows = json.loads(blob)
            if not isinstance(rows,list) or len(rows) != entry['rows'] or any(not isinstance(r,dict) for r in rows):
                raise ValueError(f'Backup record mismatch: {table}')
            for i,row in enumerate(rows):
                db.execute('INSERT INTO restored VALUES (?,?,?)', (table,i,json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False)))
            db.commit()
            restored = [json.loads(x[0]) for x in db.execute('SELECT row_json FROM restored WHERE source_table=? ORDER BY ordinal',(table,))]
            if restored != rows:
                raise ValueError(f'Rehydration mismatch: {table}')
            counts[table] = len(restored)
        db.close()
    return {'result':'PASS','mode':'ISOLATED_OFFLINE_JSON_REHYDRATION',
            'table_counts':counts,'database_writes':0,'supabase_restore_verified':False}

if __name__ == '__main__':
    print(json.dumps(rehearse(sys.argv[1]),sort_keys=True))
