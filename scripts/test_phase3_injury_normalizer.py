import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from phase3_injury_normalizer import normalize

NOW = datetime(2026, 11, 9, 18, tzinfo=timezone.utc)

def sample():
    return {'source': 'test-fixture', 'observed_at': '2026-11-09T17:00:00Z',
            'injuries': [{'team': 'BUF', 'player_id': 'player-1', 'status': 'QUESTIONABLE'}]}

class InjuryNormalizerTests(unittest.TestCase):
    def test_valid_staging_never_claims_sync(self):
        result = normalize(sample(), NOW)
        self.assertEqual(result['injury_records_validated'], 1)
        self.assertEqual(result['injury_records_written'], 0)
        self.assertFalse(result['injury_sync_complete'])
    def test_reject_missing_timestamp(self):
        data = sample(); del data['observed_at']
        with self.assertRaises(ValueError): normalize(data, NOW)
    def test_reject_naive_timestamp(self):
        data = sample(); data['observed_at'] = '2026-11-09T17:00:00'
        with self.assertRaises(ValueError): normalize(data, NOW)
    def test_reject_stale(self):
        data = sample(); data['observed_at'] = '2026-10-30T17:00:00Z'
        with self.assertRaises(ValueError): normalize(data, NOW)
    def test_reject_future(self):
        data = sample(); data['observed_at'] = '2026-11-10T17:00:00Z'
        with self.assertRaises(ValueError): normalize(data, NOW)
    def test_reject_unknown_status(self):
        data = sample(); data['injuries'][0]['status'] = 'MAYBE'
        with self.assertRaises(ValueError): normalize(data, NOW)
    def test_reject_duplicate(self):
        data = sample(); data['injuries'].append(data['injuries'][0].copy())
        with self.assertRaises(ValueError): normalize(data, NOW)
    def test_reject_missing_source(self):
        data = sample(); del data['source']
        with self.assertRaises(ValueError): normalize(data, NOW)

if __name__ == '__main__': unittest.main()
