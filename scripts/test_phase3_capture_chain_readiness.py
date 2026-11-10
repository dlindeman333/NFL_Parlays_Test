import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from phase3_capture_chain_readiness import assess


class CaptureChainReadinessTests(unittest.TestCase):
    def test_intact_capture_remains_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            raw = b'player_id,week\n123,10\n'
            (p / 'source_stats.csv').write_bytes(raw)
            (p / 'capture_manifest.json').write_text(json.dumps({
                'raw_csv_sha256': hashlib.sha256(raw).hexdigest(),
                'raw_csv_size_bytes': len(raw),
                'capture_started_utc': '2026-11-09T15:00:00Z',
                'capture_completed_utc': '2026-11-09T15:02:00Z',
                'historical_point_in_time_verified': False,
            }))
            result = assess(p)
            self.assertEqual(result['evidence_integrity'], 'PASS')
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertFalse(result['prediction_preview_compared'])
            self.assertEqual(result['cloud_writes'], 0)

    def test_tampered_capture_fails_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'source_stats.csv').write_bytes(b'wrong')
            (p / 'capture_manifest.json').write_text(json.dumps({
                'raw_csv_sha256': '0' * 64, 'raw_csv_size_bytes': 5,
                'capture_started_utc': '2026-11-09T15:00:00Z',
                'capture_completed_utc': '2026-11-09T15:02:00Z',
                'historical_point_in_time_verified': False,
            }))
            self.assertEqual(assess(p)['evidence_integrity'], 'FAIL')

    def test_missing_capture_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = assess(Path(tmp))
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertEqual(result['cloud_writes'], 0)


if __name__ == '__main__':
    unittest.main()
