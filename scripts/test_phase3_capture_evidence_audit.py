import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from phase3_capture_evidence_audit import audit_evidence

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.raw = b'player_id,week\n123,10\n'
        self.digest = hashlib.sha256(self.raw).hexdigest()
        (self.folder / 'source_stats.csv').write_bytes(self.raw)
        self.capture = {'raw_csv_sha256': self.digest, 'raw_csv_size_bytes': len(self.raw),
                        'capture_started_utc': '2026-11-09T15:00:00Z',
                        'capture_completed_utc': '2026-11-09T15:02:00Z',
                        'historical_point_in_time_verified': False}
        self.preview = {'source_sha256': self.digest, 'source_acquired_at_utc': '2026-11-09T15:01:00Z'}
        self.save()
    def save(self):
        (self.folder / 'capture_manifest.json').write_text(json.dumps(self.capture))
    def test_matching_evidence_is_still_blocked(self):
        result = audit_evidence(self.folder, self.preview)
        self.assertEqual(result['evidence_integrity'], 'PASS')
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['cloud_writes'], 0)
    def test_tampered_file(self):
        (self.folder / 'source_stats.csv').write_bytes(b'tampered')
        self.assertIn('capture_hash_or_size_mismatch', audit_evidence(self.folder, self.preview)['reasons'])
    def test_mismatched_preview(self):
        self.preview['source_sha256'] = '0' * 64
        self.assertIn('preview_source_hash_mismatch', audit_evidence(self.folder, self.preview)['reasons'])
    def test_preview_outside_window(self):
        self.preview['source_acquired_at_utc'] = '2026-11-09T16:00:00Z'
        self.assertIn('preview_outside_capture_window', audit_evidence(self.folder, self.preview)['reasons'])
    def test_missing_capture(self):
        (self.folder / 'capture_manifest.json').unlink()
        self.assertIn('capture_evidence_unavailable', audit_evidence(self.folder, self.preview)['reasons'])
    def test_invalid_capture_clock(self):
        self.capture['capture_started_utc'] = '2026-11-09T16:00:00Z'
        self.save()
        self.assertIn('invalid_capture_clock', audit_evidence(self.folder, self.preview)['reasons'])

if __name__ == '__main__':
    unittest.main()
