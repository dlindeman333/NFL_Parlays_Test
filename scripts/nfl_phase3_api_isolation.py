#!/usr/bin/env python3
"""TEST-only authenticated Supabase RLS isolation gate. Destructive to disposable A/B parlay rows only."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT = 'luxezjthznupdghmexyh'
BASE = f'https://{PROJECT}.supabase.co'
KEY = os.environ['NFL_TEST_SUPABASE_PUBLISHABLE_KEY'].strip()
if not (KEY.startswith('sb_publishable_') or KEY.startswith('eyJ')):
    raise SystemExit('FAIL: TEST publishable/anon key missing or invalid')
if os.environ.get('NFL_TEST_ALLOW_WRITE_ISOLATION') != 'YES_TEST_ONLY':
    raise SystemExit('FAIL: set NFL_TEST_ALLOW_WRITE_ISOLATION=YES_TEST_ONLY for this run')


def call(method, path, token=None, body=None, prefer=None):
    headers = {'apikey': KEY, 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if prefer:
        headers['Prefer'] = prefer
    data = None if body is None else json.dumps(body).encode('utf-8')
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        return exc.code, None


def check(ok, label):
    if not ok:
        raise AssertionError(label)
    print('PASS:', label)


def login(name):
    email = os.environ[f'NFL_TEST_USER_{name}_EMAIL']
    password = os.environ[f'NFL_TEST_USER_{name}_PASSWORD']
    status, data = call('POST', '/auth/v1/token?grant_type=password', body={'email': email, 'password': password})
    check(status == 200 and isinstance(data, dict) and data.get('access_token'), f'{name} authentication')
    token = data['access_token']
    status, identity = call('GET', '/auth/v1/user', token)
    check(status == 200 and isinstance(identity, dict) and identity.get('id'), f'{name} identity')
    check(identity['id'] == data.get('user', {}).get('id'), f'{name} token identity matches')
    return token, identity['id']


def rows(token, table, owner, fields='user_id'):
    path = f'/rest/v1/{table}?user_id=eq.{urllib.parse.quote(owner)}&select={fields}'
    return call('GET', path, token)


def parlay_path(owner):
    return '/rest/v1/nfl_parlay_sync?user_id=eq.' + urllib.parse.quote(owner)


def payload_marker(name):
    return {'phase3_security_gate': 'disposable-2026-11', 'account': name}


def main():
    a_token, a_id = login('A')
    b_token, b_id = login('B')
    check(a_id != b_id, 'Distinct authenticated user IDs')
    users = [('A', a_token, a_id, b_id), ('B', b_token, b_id, a_id)]
    for table in ('nfl_parlay_sync', 'nfl_user_prediction_tracking'):
        for name, token, own, other in users:
            status, own_rows = rows(token, table, own)
            check(status == 200 and isinstance(own_rows, list), f'{name} own {table} query allowed')
            status, foreign_rows = rows(token, table, other)
            check(status == 200 and foreign_rows == [], f'{name} cannot read other user {table}')
            print('INFO:', name, table, 'own-row-count', len(own_rows))

    # Strict preflight: neither account may have an existing parlay row.
    # A fail here stops the test BEFORE any mutation.
    for name, token, own, _ in users:
        status, existing = rows(token, 'nfl_parlay_sync', own, 'user_id,payload')
        check(status == 200 and existing == [], f'{name} parlay row absent before writes')

    created = set()
    try:
        for name, token, own, _ in users:
            status, result = call('POST', '/rest/v1/nfl_parlay_sync', token,
                body={'user_id': own, 'payload': payload_marker(name)},
                prefer='return=representation')
            # Record possible creation even if response is unexpected; cleanup checks marker.
            created.add(name)
            check(status == 201 and isinstance(result, list) and len(result) == 1
                  and result[0].get('user_id') == own
                  and result[0].get('payload') == payload_marker(name), f'{name} owner INSERT')

        for name, token, own, other in users:
            status, result = rows(token, 'nfl_parlay_sync', own, 'user_id,payload')
            check(status == 200 and len(result) == 1 and result[0]['payload'] == payload_marker(name),
                  f'{name} owner SELECT sees disposable row')
            status, result = rows(token, 'nfl_parlay_sync', other)
            check(status == 200 and result == [], f'{name} cannot SELECT foreign parlay')

            status, result = call('PATCH', parlay_path(other) + '&select=user_id', token,
                body={'payload': {'phase3_security_gate': 'ILLEGAL_FOREIGN_UPDATE'}},
                prefer='return=representation')
            check(status == 200 and result == [], f'{name} foreign UPDATE blocked')
            status, result = call('DELETE', parlay_path(other) + '&select=user_id', token,
                prefer='return=representation')
            check(status == 200 and result == [], f'{name} foreign DELETE blocked')

            status, result = call('POST', '/rest/v1/nfl_parlay_sync', token,
                body={'user_id': other, 'payload': {'phase3_security_gate': 'ILLEGAL_FOREIGN_INSERT'}},
                prefer='return=representation')
            check(status in (400, 401, 403, 409), f'{name} foreign INSERT rejected')

            status, result = call('POST', '/rest/v1/nfl_user_prediction_tracking', token,
                body={'user_id': other, 'tracking_id': 'phase3_forbidden_' + name,
                      'payload': {'phase3_security_gate': 'ILLEGAL_FOREIGN_INSERT'}},
                prefer='return=representation')
            check(status in (400, 401, 403, 409), f'{name} foreign prediction INSERT rejected')

        for name, token, own, _ in users:
            status, result = call('PATCH', parlay_path(own) + '&select=user_id,payload', token,
                body={'payload': {**payload_marker(name), 'updated': True}},
                prefer='return=representation')
            check(status == 200 and isinstance(result, list) and len(result) == 1
                  and result[0].get('payload') == {**payload_marker(name), 'updated': True},
                  f'{name} owner UPDATE')
        print('PASS: authenticated parlay INSERT/UPDATE/DELETE isolation (DELETE ownership tested)')
    finally:
        # Always attempt cleanup. Never delete rows without the exact disposable marker.
        # If a foreign-write test unexpectedly succeeded, its changed payload is NOT matched
        # by this cleanup: fail visibly and require manual inspection.
        cleanup_errors = []
        for name, token, own, _ in users:
            if name not in created:
                continue
            status, found = rows(token, 'nfl_parlay_sync', own, 'user_id,payload')
            if status != 200 or not isinstance(found, list) or len(found) != 1 or not isinstance(found[0].get('payload'), dict) or found[0]['payload'].get('phase3_security_gate') != 'disposable-2026-11' or found[0]['payload'].get('account') != name:
                cleanup_errors.append(f'{name} cleanup refused: row missing or marker mismatch')
                continue
            # Filter on BOTH owner and exact JSON marker; avoids deleting unexpected data.
            path = parlay_path(own) + '&payload->>phase3_security_gate=eq.disposable-2026-11&payload->>account=eq.' + name + '&select=user_id'
            status, deleted = call('DELETE', path, token, prefer='return=representation')
            if status != 200 or not isinstance(deleted, list) or len(deleted) != 1:
                cleanup_errors.append(f'{name} cleanup DELETE failed or unexpected count: HTTP {status}')
            else:
                status, remaining = rows(token, 'nfl_parlay_sync', own)
                if status != 200 or remaining != []:
                    cleanup_errors.append(f'{name} cleanup postcheck failed')
                else:
                    print('PASS:', name, 'disposable parlay deleted and absence verified')
        if cleanup_errors:
            raise AssertionError('; '.join(cleanup_errors))
    print('PASS: TEST authenticated parlay write isolation and cleanup')
    print('PENDING: positive prediction-tracking write isolation (requires safe cleanup design)')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, KeyError, ValueError, urllib.error.URLError) as exc:
        print('FAIL:', str(exc))
        sys.exit(1)
