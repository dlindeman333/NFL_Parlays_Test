import unittest
from datetime import datetime, timezone, timedelta
from phase3_injury_records import validate_injury_records

NOW = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)

def sample(**changes):
    data = dict(player_id='123', team='BUF', source='official-team-report', status='QUESTIONABLE', observed_at='2026-11-09T19:00:00Z')
    data.update(changes)
    return data

class InjuryRecordValidationTests(unittest.TestCase):
    def test_valid_preserves_source_and_time(self):
        record = validate_injury_records([sample()], now=NOW)[0]
        self.assertEqual(record['source'], 'official-team-report')
        self.assertEqual(record['observed_at'], '2026-11-09T19:00:00+00:00')
    def test_empty_batch_is_valid_but_not_proof_of_sync(self):
        self.assertEqual(validate_injury_records([], now=NOW), [])
    def test_missing_player(self):
        with self.assertRaisesRegex(ValueError, 'player_id'):
            validate_injury_records([sample(player_id='')], now=NOW)
    def test_missing_source(self):
        with self.assertRaisesRegex(ValueError, 'source'):
            validate_injury_records([sample(source=None)], now=NOW)
    def test_unknown_status(self):
        with self.assertRaisesRegex(ValueError, 'status'):
            validate_injury_records([sample(status='healthy-ish')], now=NOW)
    def test_stale(self):
        with self.assertRaisesRegex(ValueError, 'stale'):
            validate_injury_records([sample(observed_at='2026-10-01T19:00:00Z')], now=NOW)
    def test_future(self):
        with self.assertRaisesRegex(ValueError, 'future'):
            validate_injury_records([sample(observed_at='2026-11-10T19:00:00Z')], now=NOW)
    def test_timezone_required(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            validate_injury_records([sample(observed_at='2026-11-09T19:00:00')], now=NOW)
    def test_duplicate(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            validate_injury_records([sample(), sample(status='OUT')], now=NOW)
    def test_entire_batch_fails(self):
        with self.assertRaises(ValueError):
            validate_injury_records([sample(), sample(player_id='999', status='UNKNOWN')], now=NOW)

if __name__ == '__main__':
    unittest.main()
