import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from phase3_prediction_capture_link import assess


class PredictionCaptureLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = self.root / 'capture'
        self.capture.mkdir()
        raw = b'player,passing_yards\n1,100\n'
        self.digest = hashlib.sha256(raw).hexdigest()
        (self.capture / 'source_stats.csv').write_bytes(raw)
        self.manifest = {'raw_csv_sha256': self.digest, 'raw_csv_size_bytes': len(raw),
                         'capture_started_utc': '2026-11-09T14:00:00Z',
                         'capture_completed_utc': '2026-11-09T14:01:00Z',
                         'season': 2026, 'week': 10}
        self.preview = {'source_csv_sha256': self.digest, 'run_at_utc': '2026-11-09T14:02:00Z',
                        'season': 2026, 'week': 10, 'mode': 'READ_ONLY', 'database_writes': 0,
                        'readiness': 'BLOCKED_FOR_AUTOMATED_SNAPSHOTS',
                        'point_in_time_verified': False, 'prediction_snapshots_created': 0,
                        'grades_created': 0, 'blocking_reasons': ['upstream_row_publication_times_unverified']}
        self.save()

    def save(self):
        (self.capture / 'capture_manifest.json').write_text(json.dumps(self.manifest))
        (self.root / 'preview.json').write_text(json.dumps(self.preview))

    def run_audit(self):
        return assess(self.capture, self.root / 'preview.json')

    def test_matching_artifacts_still_block_certification(self):
        result = self.run_audit()
        self.assertEqual(result['linkage'], 'PASS')
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['cloud_writes'], 0)

    def test_wrong_source_hash(self):
        self.preview['source_csv_sha256'] = 'bad'
        self.save()
        self.assertIn('prediction_source_mismatch', self.run_audit()['reasons'])

    def test_wrong_week(self):
        self.preview['week'] = 11
        self.save()
        self.assertIn('season_week_mismatch', self.run_audit()['reasons'])

    def test_prediction_before_capture(self):
        self.preview['run_at_utc'] = '2026-11-09T13:59:00Z'
        self.save()
        self.assertIn('invalid_capture_prediction_order', self.run_audit()['reasons'])

    def test_preview_cannot_claim_verified(self):
        self.preview['point_in_time_verified'] = True
        self.save()
        self.assertIn('preview_certification_safety_violation', self.run_audit()['reasons'])

    def test_preview_cannot_claim_snapshot_writes(self):
        self.preview['prediction_snapshots_created'] = 1
        self.save()
        self.assertIn('preview_certification_safety_violation', self.run_audit()['reasons'])

    def test_preview_requires_provenance_blockers(self):
        self.preview['blocking_reasons'] = []
        self.save()
        self.assertIn('missing_preview_provenance_blockers', self.run_audit()['reasons'])

    def test_missing_preview(self):
        (self.root / 'preview.json').unlink()
        self.assertEqual(self.run_audit()['independent_prediction_compared'], False)

    def test_altered_capture(self):
        (self.capture / 'source_stats.csv').write_bytes(b'altered')
        self.assertIn('capture_content_mismatch', self.run_audit()['reasons'])

    def test_unexpected_write_mode(self):
        self.preview['database_writes'] = 1
        self.save()
        self.assertIn('unexpected_preview_mode', self.run_audit()['reasons'])


if __name__ == '__main__':
    unittest.main()
