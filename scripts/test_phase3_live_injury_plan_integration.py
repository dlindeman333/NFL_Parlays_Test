"""Live feed planning remains fail-closed and never writes cloud records."""
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import phase3_weekly_injury_preview as module


class LivePlanIntegrationTests(unittest.TestCase):
    def test_live_plan_requires_both_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'observations.json'
            report = Path(d) / 'report.json'
            with patch.object(module, 'get_scoreboard', return_value={'events': []}), \
                 patch.object(module, 'ingest', return_value={
                     'records': [], 'source_url': 'https://example.org/injury',
                     'sha256': 'abc', 'validated_records': 0}), \
                 patch.dict(os.environ, {
                     'NFL_PHASE3_INJURY_FEED_URL': 'https://example.org/injury',
                     'NFL_PHASE3_INJURY_FEED_HOST': 'example.org',
                     'NFL_PHASE3_INJURY_VALIDATED_OUTPUT': str(output),
                     'NFL_PHASE3_INJURY_REPORT': str(report),
                     'NFL_PHASE3_INJURY_LIVE_EXISTING': str(Path(d) / 'old.json'),
                     'NFL_PHASE3_INJURY_LIVE_COVERAGE_EVIDENCE': '',
                     'NFL_PHASE3_INJURY_OBSERVATIONS': '',
                 }):
                with self.assertRaisesRegex(ValueError, 'both existing records and coverage evidence'):
                    module.main()
            self.assertFalse(report.exists())

    def test_attestation_must_match_live_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            observations = root / 'observations.json'
            evidence = root / 'evidence.json'
            old = root / 'old.json'
            old.write_text('[]')
            records = [{'player_id':'p1', 'team':'BUF', 'status':'QUESTIONABLE',
                        'source':'https://example.org/injury',
                        'observed_at': datetime.now(timezone.utc).isoformat()}]
            raw = json.dumps(records, indent=2) + '\n'
            evidence.write_text(json.dumps({
                'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'coverage': 'FULL_NFL_INJURY_FEED', 'independently_verified': True,
                'source_url': 'https://wrong.example.org/injury',
                'verified_by': 'external-review', 'season': 2026, 'week': 10,
                'verified_at': datetime.now(timezone.utc).isoformat()}))
            with patch.object(module, 'get_scoreboard', return_value={'events': []}), \
                 patch.object(module, 'ingest', return_value={
                     'records': records, 'source_url': 'https://example.org/injury',
                     'sha256': 'abc', 'validated_records': 1}), \
                 patch.dict(os.environ, {
                     'NFL_PHASE3_INJURY_FEED_URL': 'https://example.org/injury',
                     'NFL_PHASE3_INJURY_FEED_HOST': 'example.org',
                     'NFL_PHASE3_INJURY_VALIDATED_OUTPUT': str(observations),
                     'NFL_PHASE3_INJURY_REPORT': str(root / 'report.json'),
                     'NFL_PHASE3_INJURY_LIVE_EXISTING': str(old),
                     'NFL_PHASE3_INJURY_LIVE_COVERAGE_EVIDENCE': str(evidence),
                     'NFL_PHASE3_INJURY_OBSERVATIONS': '',
                 }):
                with self.assertRaisesRegex(ValueError, 'source differs'):
                    module.main()
            self.assertFalse((root / 'report.json').exists())


if __name__ == '__main__':
    unittest.main()
