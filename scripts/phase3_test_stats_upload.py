#!/usr/bin/env python3
"""Validate NFL stats and optionally upsert a single season into pinned TEST Supabase.

Safe by default: without --upload, validates locally and performs no network writes.
On upload, checks existing season for regressions and verifies the read-back.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

TEST_HOST = 'luxezjthznupdghmexyh.supabase.co'
TEST_REPO = 'dlindeman333/NFL_Parlays_Test'
REQUIRED = {'season', 'week', 'player_id', 'team', 'game_status', 'game_date'}
MAX_BYTES = 12_000_000


def validate(path, season=2026):
    raw = Path(path).read_bytes()
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('empty_or_oversized_csv')
    text = raw.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or ())
    if not REQUIRED.issubset(headers):
        raise ValueError('missing_headers: ' + ','.join(sorted(REQUIRED - headers)))
    count = completed = scheduled = 0
    identities = set()
    completed_weeks = set()
    for row in reader:
        count += 1
        if row['season'] != str(season):
            raise ValueError('unexpected_season')
        if not row['player_id'] or not row['team'] or not row['week']:
            raise ValueError('missing_identity')
        try:
            week = int(row['week'])
        except (TypeError, ValueError):
            raise ValueError('invalid_week') from None
        if not 1 <= week <= 22:
            raise ValueError('invalid_week')
        status = row['game_status']
        if status not in ('COMPLETED', 'SCHEDULED'):
            raise ValueError('unexpected_game_status')
        if status == 'COMPLETED':
            completed += 1
            completed_weeks.add(week)
        else:
            scheduled += 1
        # Player-week-game-date distinguishes possible multiple games in a week.
        identity = (row['player_id'], row['team'], row['week'], row['game_date'], status)
        if identity in identities:
            raise ValueError('duplicate_player_game_row')
        identities.add(identity)
    if count == 0 or completed == 0:
        raise ValueError('no_completed_player_stats')
    return {'season': season, 'record_count': count, 'completed': completed,
            'scheduled': scheduled, 'completed_weeks': sorted(completed_weeks),
            'sha256': hashlib.sha256(raw).hexdigest(), 'csv_text': text}


def check_test_boundary(url, repo):
    p = parse.urlsplit(url)
    if (p.scheme != 'https' or p.hostname != TEST_HOST or p.path not in ('', '/')
            or p.query or p.fragment or p.username or p.password or p.port):
        raise ValueError('refusing_non_test_supabase_url')
    if repo != TEST_REPO:
        raise ValueError('refusing_non_test_repository')


def api_request(url, key, method, endpoint, payload=None, prefer=None):
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key,
               'Accept': 'application/json'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    if prefer:
        headers['Prefer'] = prefer
    req = request.Request(url.rstrip('/') + '/rest/v1/' + endpoint,
                          data=payload, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=120) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError('unexpected_supabase_status')
            body = resp.read()
            return json.loads(body) if body else None
    except error.HTTPError as exc:
        # Do not expose potentially sensitive response content or credentials.
        raise RuntimeError('supabase_http_error_' + str(exc.code)) from None


def compare_existing(existing, incoming):
    if not existing:
        return 'first_upload'
    old_text = existing.get('csv_text') or ''
    old = csv.DictReader(io.StringIO(old_text))
    old_completed = 0
    old_weeks = set()
    for row in old:
        if row.get('game_status') == 'COMPLETED':
            old_completed += 1
            try:
                old_weeks.add(int(row['week']))
            except (TypeError, ValueError, KeyError):
                raise ValueError('existing_export_invalid_week') from None
    if incoming['record_count'] < int(existing.get('record_count') or 0):
        raise ValueError('refusing_record_count_regression')
    if incoming['completed'] < old_completed:
        raise ValueError('refusing_completed_count_regression')
    if not old_weeks.issubset(set(incoming['completed_weeks'])):
        raise ValueError('refusing_completed_week_regression')
    return 'non_regressive'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', default='nfl_player_stats.csv')
    parser.add_argument('--season', type=int, default=2026)
    parser.add_argument('--upload', action='store_true')
    args = parser.parse_args()
    report = validate(args.csv, args.season)
    print(json.dumps({k: v for k, v in report.items() if k != 'csv_text'}, indent=2))
    if not args.upload:
        print('PREVIEW ONLY: no database writes')
        return
    url = os.environ.get('SUPABASE_URL', '')
    check_test_boundary(url, os.environ.get('GITHUB_REPOSITORY', ''))
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not key:
        raise ValueError('missing_test_service_role_key')
    endpoint = ('nfl_stat_exports?season=eq.' + str(args.season)
                + '&select=season,record_count,csv_text')
    existing_rows = api_request(url, key, 'GET', endpoint)
    if not isinstance(existing_rows, list) or len(existing_rows) > 1:
        raise RuntimeError('unexpected_existing_season_response')
    existing = existing_rows[0] if existing_rows else None
    comparison = compare_existing(existing, report)
    if existing and hashlib.sha256((existing.get('csv_text') or '').encode('utf-8')).hexdigest() == report['sha256']:
        print('TEST export already matches CSV: no database write needed')
        return
    print('Existing export check passed:', comparison)
    payload = json.dumps({'season': args.season,
                          'record_count': report['record_count'],
                          'generated_at': datetime.now(timezone.utc).isoformat(),
                          'csv_text': report['csv_text']}, allow_nan=False).encode('utf-8')
    api_request(url, key, 'POST', 'nfl_stat_exports?on_conflict=season', payload,
                'resolution=merge-duplicates,return=minimal')
    after_rows = api_request(url, key, 'GET', endpoint)
    if not isinstance(after_rows, list) or len(after_rows) != 1:
        raise RuntimeError('upload_readback_missing_or_ambiguous')
    after = after_rows[0]
    after_hash = hashlib.sha256((after.get('csv_text') or '').encode('utf-8')).hexdigest()
    if after_hash != report['sha256'] or int(after.get('record_count') or 0) != report['record_count']:
        raise RuntimeError('upload_readback_mismatch')
    print('TEST statistics export uploaded and read-back verified successfully')


if __name__ == '__main__':
    main()
