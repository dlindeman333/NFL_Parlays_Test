import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from phase3_weekly_injury_preview import summarize, main


class InjuryPreviewTests(unittest.TestCase):
    def test_no_injury_sync_claim_or_writes(self):
        result = summarize({'events': [{'id': '42'}, {'id': '43'}]})
        self.assertEqual(result['event_ids'], ['42', '43'])
        self.assertEqual(result['injury_records_written'], 0)
        self.assertFalse(result['injury_sync_complete'])
    def test_optional_sync_plan_requires_explicit_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            obs = root / 'obs.json'
            old = root / 'old.json'
            out = root / 'report.json'
            obs.write_text(json.dumps([{'player_id': '1', 'team': 'BUF', 'source': 'team-report', 'status': 'OUT', 'observed_at': '2026-11-09T19:00:00Z'}]))
            old.write_text('[]')
            env = {'NFL_PHASE3_INJURY_OBSERVATIONS': str(obs), 'NFL_PHASE3_INJURY_EXISTING': str(old), 'NFL_PHASE3_INJURY_REPORT': str(out)}
            with patch.dict(os.environ, env, clear=True), patch('phase3_weekly_injury_preview.get_scoreboard', return_value={'events': []}), patch('phase3_weekly_injury_preview.validate_injury_records', return_value=[{'source':'team-report'}]):
                main()
                result = json.loads(out.read_text())
                self.assertIn('sync_plan_blocked', result)
                self.assertNotIn('sync_plan', result)
                self.assertEqual(result['injury_records_written'], 0)

    def test_optional_live_feed_is_read_only_and_not_coverage_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'report.json'
            env = {'NFL_PHASE3_INJURY_FEED_URL': 'https://injuries.example.org/data',
                   'NFL_PHASE3_INJURY_FEED_HOST': 'injuries.example.org',
                   'NFL_PHASE3_INJURY_REPORT': str(out)}
            fake = {'source_url': env['NFL_PHASE3_INJURY_FEED_URL'], 'sha256': 'a' * 64,
                    'validated_records': 3, 'records': [], 'injury_records_written': 0}
            with patch.dict(os.environ, env, clear=True), \
                 patch('phase3_weekly_injury_preview.get_scoreboard', return_value={'events': []}), \
                 patch('phase3_weekly_injury_preview.ingest', return_value=fake) as fetch:
                main()
                fetch.assert_called_once_with(env['NFL_PHASE3_INJURY_FEED_URL'], env['NFL_PHASE3_INJURY_FEED_HOST'])
                report = json.loads(out.read_text())
                self.assertEqual(report['live_injury_feed']['validated_records'], 3)
                self.assertFalse(report['live_injury_feed']['coverage_independently_verified'])
                self.assertEqual(report['injury_records_written'], 0)
                self.assertFalse(report['injury_sync_complete'])

    def test_live_feed_requires_both_configuration_values(self):
        with patch.dict(os.environ, {'NFL_PHASE3_INJURY_FEED_URL': 'https://injuries.example.org/data'}, clear=True), \
             patch('phase3_weekly_injury_preview.get_scoreboard', return_value={'events': []}):
            with self.assertRaisesRegex(ValueError, 'Both injury feed'):
                main()

    def test_rejects_unexpected_payload(self):
        with self.assertRaises(ValueError):
            summarize({'error': 'bad response'})

if __name__ == '__main__':
    unittest.main()
