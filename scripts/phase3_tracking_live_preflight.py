"""TEST-only authenticated, read-only Supabase preflight for prediction tracking.

Never sends POST/PATCH/PUT/DELETE. Does not log tokens or user data.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from uuid import UUID

TEST_PROJECT = 'luxezjthznupdghmexyh'


def _get_json(url, key, token, opener):
    request = urllib.request.Request(url, headers={
        'apikey': key, 'Authorization': 'Bearer ' + token,
        'Accept': 'application/json',
    }, method='GET')
    with opener(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError('Unexpected Supabase response status')
        return json.load(response)


def preflight(base_url, key, token, expected_user, repository, opener=urllib.request.urlopen, record_sink=None):
    if repository != 'dlindeman333/NFL_Parlays_Test':
        raise ValueError('Only the designated TEST repository is permitted')
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != 'https' or parsed.hostname != TEST_PROJECT + '.supabase.co'
            or parsed.port is not None or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise ValueError('Only the exact TEST Supabase project URL is permitted')
    if not key or not token:
        raise ValueError('Publishable key and authenticated user token required')
    try:
        user_id = str(UUID(expected_user))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Expected user must be a UUID') from exc
    origin = 'https://' + parsed.hostname
    identity = _get_json(origin + '/auth/v1/user', key, token, opener)
    if not isinstance(identity, dict) or identity.get('id') != user_id:
        raise ValueError('Authenticated identity does not match expected user')
    # Supabase/PostgREST can cap responses at 1,000 rows. Never silently
    # treat the first page as the user's complete tracking history.
    page_size = 1000
    seen = set()
    total = 0
    for page in range(100):
        query = urllib.parse.urlencode({
            'select': 'tracking_id,payload,user_id',
            'user_id': 'eq.' + user_id,
            'order': 'tracking_id.asc',
            'limit': str(page_size),
            'offset': str(page * page_size),
        })
        rows = _get_json(origin + '/rest/v1/nfl_user_prediction_tracking?' + query, key, token, opener)
        if not isinstance(rows, list) or len(rows) > page_size:
            raise ValueError('Unexpected tracking page response')
        for record in rows:
            if not isinstance(record, dict) or record.get('user_id') != user_id:
                raise ValueError('Unexpected tracking response or owner mismatch')
            tracking_id = record.get('tracking_id')
            if not isinstance(tracking_id, str) or not tracking_id or tracking_id in seen:
                raise ValueError('Missing or duplicate tracking ID across pages')
            seen.add(tracking_id)
            if record_sink is not None:
                record_sink(record)
        total += len(rows)
        if len(rows) < page_size:
            break
    else:
        raise ValueError('Tracking history exceeds audited pagination limit')
    return {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT', 'authenticated_owner_verified': True,
            'visible_tracking_records': total, 'database_writes': 0,
            'ready_for_write_activation': False}



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-user', required=True)
    args = parser.parse_args()
    result = preflight(os.environ.get('NFL_TEST_SUPABASE_URL', ''),
                       os.environ.get('NFL_TEST_SUPABASE_PUBLISHABLE_KEY', ''),
                       os.environ.get('NFL_TEST_USER_ACCESS_TOKEN', ''),
                       args.expected_user, os.environ.get('GITHUB_REPOSITORY', ''))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
