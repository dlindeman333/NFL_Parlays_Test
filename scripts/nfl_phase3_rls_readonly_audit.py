"""Catalog-only Supabase RLS audit. No DML, DDL, or user row reads."""
import json
import os
import sys
from pathlib import Path

import psycopg

OUTPUT = Path('rls-audit-report.json')
TABLES = ('nfl_parlay_sync', 'nfl_prediction_tracking')


def main():
    url = os.environ.get('NFL_TEST_DATABASE_URL', '')
    if not url:
        raise SystemExit('Missing NFL_TEST_DATABASE_URL repository secret (TEST DB only).')
    report = {'scope': 'TEST database (operator supplied)', 'mode': 'catalog-only/read-only', 'tables': [], 'warnings': []}
    # Transaction-level READ ONLY blocks writes even if the supplied role has write privileges.
    with psycopg.connect(url, connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=15000') as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
                cur.execute('SELECT current_database(), current_user')
                report['database'], report['database_role'] = cur.fetchone()
                for table in TABLES:
                    cur.execute('''SELECT c.oid, c.relrowsecurity, c.relforcerowsecurity, c.relowner::regrole::text
                                   FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                                   WHERE n.nspname='public' AND c.relname=%s AND c.relkind IN ('r','p')''', (table,))
                    row = cur.fetchone()
                    if not row:
                        report['tables'].append({'name': table, 'status': 'MISSING'})
                        report['warnings'].append(f'{table}: missing; verify expected schema/table name')
                        continue
                    oid, enabled, forced, owner = row
                    cur.execute('''SELECT policyname, permissive, roles, cmd, qual, with_check
                                   FROM pg_policies WHERE schemaname='public' AND tablename=%s
                                   ORDER BY policyname''', (table,))
                    policies = [dict(zip(('name','permissive','roles','command','using','with_check'), p)) for p in cur.fetchall()]
                    cur.execute('''SELECT a.attname FROM pg_attribute a
                                   WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped
                                   ORDER BY a.attnum''', (oid,))
                    columns = [r[0] for r in cur.fetchall()]
                    cur.execute('''SELECT indexname, indexdef FROM pg_indexes
                                   WHERE schemaname='public' AND tablename=%s ORDER BY indexname''', (table,))
                    indexes = [{'name': n, 'definition': d} for n, d in cur.fetchall()]
                    item = {'name': table, 'rls_enabled': enabled, 'force_rls': forced,
                            'owner_role': owner, 'columns': columns, 'policies': policies, 'indexes': indexes}
                    report['tables'].append(item)
                    if not enabled:
                        report['warnings'].append(f'{table}: RLS IS DISABLED')
                    if not policies:
                        report['warnings'].append(f'{table}: no policies configured')
                    if any(p['command'] == 'ALL' and p['using'] in ('true', '(true)', None) for p in policies):
                        report['warnings'].append(f'{table}: review permissive ALL policy')
    report['result'] = 'REVIEW_REQUIRED' if report['warnings'] else 'CATALOG_CHECK_COMPLETE_MANUAL_REVIEW_REQUIRED'
    OUTPUT.write_text(json.dumps(report, indent=2, default=str) + '\n')
    print(json.dumps({'result': report['result'], 'tables': [t['name'] for t in report['tables']], 'warnings': report['warnings']}, indent=2))
    print('NOTE: Catalog inspection does not prove cross-account isolation. Separate authenticated two-user tests are required.')
    if report['warnings']:
        sys.exit(1)


if __name__ == '__main__':
    main()
