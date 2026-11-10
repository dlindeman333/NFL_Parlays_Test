"""Manual TEST-only, read-only end-to-end prediction-history authentication smoke test.

Uses existing A/B TEST credentials. Never writes tracking or parlay rows.
"""
import json
import os
import urllib.request
import urllib.parse

from phase3_tracking_live_preflight import TEST_PROJECT, preflight

BASE = f'https://{TEST_PROJECT}.supabase.co'
REPOSITORY = 'dlindeman333/NFL_Parlays_Test'


def authenticate(email, password, key, opener=urllib.request.urlopen):
    if not email or not password or not key:
        raise ValueError('Missing TEST authentication credentials')
    req = urllib.request.Request(
        BASE + '/auth/v1/token?grant_type=password',
        data=json.dumps({'email': email, 'password': password}).encode(),
        headers={'apikey': key, 'Content-Type': 'application/json'}, method='POST')
    with opener(req, timeout=15) as response:
        if response.status != 200:
            raise ValueError('TEST authentication failed')
        result = json.load(response)
    if not isinstance(result, dict) or not result.get('access_token') or not isinstance(result.get('user'), dict) or not result['user'].get('id'):
        raise ValueError('Invalid TEST authentication response')
    return result['access_token'], result['user']['id']


def verify_cross_owner_denied(key, token, other_owner, opener=urllib.request.urlopen):
    """Confirm the signed-in user cannot see the other account's tracking rows."""
    query = urllib.parse.urlencode({'select': 'tracking_id', 'user_id': 'eq.' + other_owner, 'limit': '1'})
    req = urllib.request.Request(BASE + '/rest/v1/nfl_user_prediction_tracking?' + query,
        headers={'apikey': key, 'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}, method='GET')
    with opener(req, timeout=15) as response:
        if response.status != 200:
            raise ValueError('Cross-owner tracking read returned unexpected status')
        rows = json.load(response)
    if rows != []:
        raise ValueError('Cross-owner tracking history visible: RLS isolation failed')
    return True


def run(environment=None, opener=urllib.request.urlopen):
    env = os.environ if environment is None else environment
    if env.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise ValueError('Refusing to run outside designated TEST repository')
    if env.get('NFL_TEST_SUPABASE_URL', '').rstrip('/') != BASE:
        raise ValueError('Refusing to run against non-TEST Supabase URL')
    key = env.get('NFL_TEST_SUPABASE_PUBLISHABLE_KEY', '')
    results = {}
    owners = []
    tokens = []
    for name in ('A', 'B'):
        token, owner = authenticate(env.get(f'NFL_TEST_USER_{name}_EMAIL', ''),
                                    env.get(f'NFL_TEST_USER_{name}_PASSWORD', ''), key, opener)
        report = preflight(BASE, key, token, owner, REPOSITORY, opener=opener)
        if report.get('authenticated_owner_verified') is not True or report.get('database_writes') != 0:
            raise ValueError('Authenticated read-only preflight failed')
        owners.append(owner)
        tokens.append(token)
        results[name] = {'authenticated': True, 'visible_tracking_records': report['visible_tracking_records']}
    if owners[0] == owners[1]:
        raise ValueError('TEST users must have distinct identities')
    verify_cross_owner_denied(key, tokens[0], owners[1], opener=opener)
    verify_cross_owner_denied(key, tokens[1], owners[0], opener=opener)
    # Empty owner histories cannot prove RLS isolation: both cross-owner
    # requests would return [] even with RLS disabled. Report inconclusive.
    evidence = ('INCONCLUSIVE_EMPTY_HISTORIES' if all(
        account['visible_tracking_records'] == 0 for account in results.values()
    ) else 'PARTIAL_READ_ONLY_EVIDENCE')
    return {'mode': 'TEST_TRACKING_LIVE_READ_ONLY_SMOKE', 'database_writes': 0,
            'cross_owner_read_checks': 2, 'rls_evidence': evidence,
            'write_isolation_verified': False, 'accounts': results}


if __name__ == '__main__':
    report = run()
    print(json.dumps(report, sort_keys=True))
    if report['rls_evidence'] == 'INCONCLUSIVE_EMPTY_HISTORIES':
        raise SystemExit('Read-only TEST RLS check inconclusive: no existing tracking rows')
