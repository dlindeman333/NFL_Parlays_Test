import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from phase3_injury_feed_evidence import verify_feed_evidence

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.obs = Path(self.tmp.name) / 'observations.json'
        self.evd = Path(self.tmp.name) / 'evidence.json'
        self.obs.write_text('[{"player_id":"1"}]')
        self.data = {'sha256': hashlib.sha256(self.obs.read_bytes()).hexdigest(),
                     'coverage': 'FULL_NFL_INJURY_FEED', 'independently_verified': True,
                     'source_url': 'https://example.org/injuries', 'verified_by': 'external-feed-audit',
                     'season': 2026, 'week': 10, 'verified_at': datetime.now(timezone.utc).isoformat()}
    def check(self):
        self.evd.write_text(json.dumps(self.data))
        return verify_feed_evidence(self.obs, self.evd)
    def test_valid_attestation(self):
        self.assertFalse(self.check()['cloud_writes_enabled'])
    def test_mismatched_hash(self):
        self.data['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'does not match'): self.check()
    def test_unverified(self):
        self.data['independently_verified'] = False
        with self.assertRaisesRegex(ValueError, 'independent'): self.check()
    def test_incomplete(self):
        self.data['coverage'] = 'PARTIAL'
        with self.assertRaisesRegex(ValueError, 'full NFL'): self.check()
    def test_stale(self):
        self.data['verified_at'] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        with self.assertRaisesRegex(ValueError, 'stale'): self.check()
    def test_timezone_required(self):
        self.data['verified_at'] = '2026-11-09T12:00:00'
        with self.assertRaisesRegex(ValueError, 'timezone'): self.check()
    def test_missing_week(self):
        del self.data['week']
        with self.assertRaisesRegex(ValueError, 'missing'): self.check()

if __name__ == '__main__': unittest.main()
