#!/usr/bin/env python3
"""Validate an NFL stats CSV and optionally upload it to the pinned TEST project."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

TEST_HOST = 'luxezjthznupdghmexyh.supabase.co'
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
    count, completed, scheduled = 0, 0, 0
    for row in reader:
        count += 1
        if row['season'] != str(season):
            raise ValueError('unexpected_season')
        if not row['player_id'] or not row['team'] or not row['week']:
            raise ValueError('missing_identity')
        status = row['game_status']
        if status not in ('COMPLETED', 'SCHEDULED'):
            raise ValueError('unexpected_game_status')
        if status == 'COMPLETED':
            completed += 1
        else:
            scheduled += 1
    if count == 0 or completed == 0:
        raise ValueError('no_completed_player_stats')
    return {'season': season, 'record_count': count, 'completed': completed,
            'scheduled': scheduled, 'sha256': hashlib.sha256(raw).hexdigest(), 'csv_text': text}


def check_test_boundary(url, repo):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname != TEST_HOST or p.path not in ('', '/') or p.query or p.fragment or p.username or p.password or p.port:
        raise ValueError('refusing_non_test_supabase_url')
    if repo != 'dlindeman333/NFL_Parlays_Test':
        raise ValueError('refusing_non_test_repository')


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
    payload = json.dumps({'season': args.season, 'record_count': report['record_count'],
                          'generated_at': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                          'csv_text': report['csv_text']}, allow_nan=False).encode('utf-8')
    request = urllib.request.Request(url.rstrip('/') + '/rest/v1/nfl_stat_exports?on_conflict=season',
                                     data=payload, method='POST', headers={
                                         'apikey': key, 'Authorization': 'Bearer ' + key,
                                         'Content-Type': 'application/json',
                                         'Prefer': 'resolution=merge-duplicates,return=minimal'})
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status not in (200, 201, 204):
            raise RuntimeError('unexpected_upload_status')
    print('TEST statistics export uploaded successfully')


if __name__ == '__main__':
    main()
