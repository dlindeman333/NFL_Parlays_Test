#!/usr/bin/env python3
"""TEST-only, read-only Supabase authenticated API isolation gate."""
import json
import os
import sys
import urllib.error
import urllib.request

PROJECT = 'luxezjthznupdghmexyh'
BASE = f'https://{PROJECT}.supabase.co'
KEY = os.environ['NFL_TEST_SUPABASE_PUBLISHABLE_KEY'].strip()
if not (KEY.startswith('sb_publishable_') or KEY.startswith('eyJ')):
    raise SystemExit('FAIL: TEST publishable/anon key missing or invalid')

def call(method, path, token=None, body=None):
    headers = {'apikey': KEY, 'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        return exc.code, None

def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print('PASS:', label)

def login(name):
    email = os.environ[f'NFL_TEST_USER_{name}_EMAIL']
    password = os.environ[f'NFL_TEST_USER_{name}_PASSWORD']
    status, data = call('POST', '/auth/v1/token?grant_type=password',
        body={'email': email, 'password': password})
    check(status == 200 and isinstance(data, dict) and data.get('access_token'), f'{name} authentication')
    token = data['access_token']
    status, identity = call('GET', '/auth/v1/user', token)
    check(status == 200 and isinstance(identity, dict) and identity.get('id'), f'{name} identity')
    check(identity['id'] == data.get('user', {}).get('id'), f'{name} token identity matches')
    return token, identity['id']

def get_rows(token, table, owner):
    return call('GET', f'/rest/v1/{table}?user_id=eq.{owner}&select=user_id', token)

def main():
    a_token, a_id = login('A')
    b_token, b_id = login('B')
    check(a_id != b_id, 'Distinct authenticated user IDs')
    for table in ('nfl_parlay_sync', 'nfl_user_prediction_tracking'):
        for name, token, own, other in (('A',a_token,a_id,b_id),('B',b_token,b_id,a_id)):
            status, own_rows = get_rows(token, table, own)
            check(status == 200 and isinstance(own_rows, list), f'{name} own {table} query allowed')
            status, foreign_rows = get_rows(token, table, other)
            check(status == 200 and foreign_rows == [], f'{name} cannot read other user {table}')
            # We deliberately do not assert own rows exist: the account may have no records.
            print('INFO:',name,table,'own-row-count',len(own_rows))
    print('PASS: real authenticated API READ isolation')
    print('PENDING: authenticated API INSERT, UPDATE and DELETE checks (no safe automated cleanup yet)')

if __name__ == '__main__':
    try:
        main()
    except (AssertionError, KeyError, ValueError, urllib.error.URLError) as exc:
        print('FAIL:', str(exc))
        sys.exit(1)
