#!/usr/bin/env python3
"""Read-only weekly NFL injury feed preview; never writes to Supabase.

An ESPN feed preview is NOT a validated weekly injury sync. The output is
informational and must not be treated as authoritative injury eligibility.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from phase3_injury_records import validate_injury_records
from phase3_injury_sync_plan import build_sync_plan
from phase3_injury_feed_evidence import verify_feed_evidence
from phase3_injury_live_ingest import ingest

FEED_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'


def get_scoreboard(fetch=urlopen):
    request = Request(FEED_URL, headers={'User-Agent': 'NFL-Parlay-TEST-ReadOnly/1.0'})
    with fetch(request, timeout=20) as response:
        return json.load(response)


def summarize(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
        raise ValueError('Unexpected scoreboard response; refusing to report success')
    events = payload['events']
    return {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'mode': 'READ_ONLY_PREVIEW',
        'source': 'ESPN public NFL scoreboard',
        'events_seen': len(events),
        'event_ids': [str(e['id']) for e in events if isinstance(e, dict) and e.get('id')],
        'injury_records_written': 0,
        'injury_sync_complete': False,
        'note': 'Scoreboard availability alone does not validate player injury reports or weekly sync.',
    }


def main():
    report = summarize(get_scoreboard())
    # Optional allowlisted HTTPS feed. Validation does not imply complete coverage.
    feed_url = os.environ.get('NFL_PHASE3_INJURY_FEED_URL', '').strip()
    feed_host = os.environ.get('NFL_PHASE3_INJURY_FEED_HOST', '').strip()
    if feed_url or feed_host:
        if not (feed_url and feed_host):
            raise ValueError('Both injury feed URL and allowlisted host must be configured')
        ingestion = ingest(feed_url, feed_host)
        # Preserve validated observations as a reproducible, read-only artifact.
        # No completeness assertion or cloud write is implied.
        validated_path = Path(os.environ.get('NFL_PHASE3_INJURY_VALIDATED_OUTPUT', 'phase3-injury-validated-observations.json'))
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        validated_path.write_text(json.dumps(ingestion['records'], indent=2) + '\n', encoding='utf-8')
        report['live_injury_feed'] = {
            'source_url': ingestion['source_url'],
            'validated_output': str(validated_path),
            'sha256': ingestion['sha256'],
            'validated_records': ingestion['validated_records'],
            'coverage_independently_verified': False,
            'injury_records_written': 0,
        }
        # Live observations can be compared against existing records, but only
        # with evidence bound to the exact saved bytes and configured source.
        live_existing = os.environ.get('NFL_PHASE3_INJURY_LIVE_EXISTING', '').strip()
        live_evidence = os.environ.get('NFL_PHASE3_INJURY_LIVE_COVERAGE_EVIDENCE', '').strip()
        if live_existing or live_evidence:
            if not (live_existing and live_evidence):
                raise ValueError('Live comparison requires both existing records and coverage evidence')
            coverage = verify_feed_evidence(validated_path, live_evidence)
            if coverage['source_url'] != ingestion['source_url']:
                raise ValueError('Coverage attestation source differs from live feed URL')
            existing = json.loads(Path(live_existing).read_text(encoding='utf-8'))
            report['live_injury_feed']['coverage_evidence'] = coverage
            report['live_injury_feed']['sync_plan'] = build_sync_plan(
                ingestion['records'], existing, feed_complete=True)
            report['live_injury_feed']['coverage_independently_verified'] = False
    # Optional externally sourced observation file for offline validation only.
    # The scoreboard is not an injury feed and is never treated as one.
    observations_path = os.environ.get('NFL_PHASE3_INJURY_OBSERVATIONS')
    if observations_path:
        observations = json.loads(Path(observations_path).read_text(encoding='utf-8'))
        accepted = validate_injury_records(observations)
        report['validated_observations'] = len(accepted)
        report['observation_sources'] = sorted({item['source'] for item in accepted})
        report['injury_sync_complete'] = False
        report['injury_records_written'] = 0
        existing_path = os.environ.get('NFL_PHASE3_INJURY_EXISTING')
        if existing_path:
            # Coverage is NOT inferred from the scoreboard or the presence of files.
            # Only an independently verified full-feed input may request a plan.
            evidence_path = os.environ.get('NFL_PHASE3_INJURY_COVERAGE_EVIDENCE')
            complete = bool(evidence_path)
            if complete:
                report['coverage_evidence'] = verify_feed_evidence(observations_path, evidence_path)
            existing = json.loads(Path(existing_path).read_text(encoding='utf-8'))
            if complete:
                report['sync_plan'] = build_sync_plan(observations, existing, feed_complete=True)
            else:
                report['sync_plan_blocked'] = 'Full injury feed coverage has not been independently verified'
    out = Path(os.environ.get('NFL_PHASE3_INJURY_REPORT', 'phase3-injury-preview-report.json'))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Read-only injury readiness preview: {report['events_seen']} scoreboard events; zero writes")


if __name__ == '__main__':
    main()
