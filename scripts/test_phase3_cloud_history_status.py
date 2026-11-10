"""Guard against presenting unverified cloud history as authentic pregame data."""
import pathlib
import unittest

HTML = pathlib.Path(__file__).resolve().parents[1] / 'index.html'


class CloudHistoryStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding='utf-8')

    def test_unverified_local_snapshot_explicit(self):
        self.assertIn("'Unverified local snapshot'", self.html)
        self.assertIn("payload.kind==='local_snapshot'", self.html)

    def test_verified_status_requires_capture_evidence(self):
        self.assertIn("rawStatus==='verified_pregame' && payload.capture_evidence", self.html)

    def test_unknown_status_not_misrepresented(self):
        self.assertIn("'Stored — verification not established'", self.html)

    def test_tracking_writes_remain_disabled(self):
        self.assertIn('const CLOUD_TRACKING_WRITES_ENABLED=false;', self.html)


if __name__ == '__main__':
    unittest.main()
