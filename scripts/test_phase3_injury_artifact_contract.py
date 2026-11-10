"""Regression checks for read-only validated injury feed artifacts."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import phase3_weekly_injury_preview as preview

class InjuryArtifactContract(unittest.TestCase):
    def test_live_feed_emits_validated_artifact_without_sync_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'report.json'
            observations = Path(directory) / 'validated.json'
            env = {'NFL_PHASE3_INJURY_FEED_URL': 'https://injuries.example.org/feed',
                   'NFL_PHASE3_INJURY_FEED_HOST': 'injuries.example.org',
                   'NFL_PHASE3_INJURY_REPORT': str(out),
                   'NFL_PHASE3_INJURY_VALIDATED_OUTPUT': str(observations)}
            fake = {'source_url': env['NFL_PHASE3_INJURY_FEED_URL'], 'sha256': 'abc',
                    'validated_records': 1, 'records': [{'player_id': '123', 'status': 'OUT'}]}
            with patch.dict(os.environ, env), patch.object(preview, 'get_scoreboard', return_value={'events': []}), patch.object(preview, 'ingest', return_value=fake):
                preview.main()
            self.assertEqual(json.loads(observations.read_text()), fake['records'])
            report = json.loads(out.read_text())
            self.assertFalse(report['injury_sync_complete'])
            self.assertEqual(report['injury_records_written'], 0)
            self.assertFalse(report['live_injury_feed']['coverage_independently_verified'])
            self.assertEqual(report['live_injury_feed']['validated_output'], str(observations))
    def test_no_live_feed_does_not_create_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / 'validated.json'
            env = {'NFL_PHASE3_INJURY_FEED_URL': '', 'NFL_PHASE3_INJURY_FEED_HOST': '',
                   'NFL_PHASE3_INJURY_REPORT': str(Path(directory) / 'report.json'),
                   'NFL_PHASE3_INJURY_VALIDATED_OUTPUT': str(observations)}
            with patch.dict(os.environ, env), patch.object(preview, 'get_scoreboard', return_value={'events': []}):
                preview.main()
            self.assertFalse(observations.exists())

if __name__ == '__main__': unittest.main()
