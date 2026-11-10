from pathlib import Path
import unittest

HTML = Path(__file__).resolve().parents[1].joinpath('index.html').read_text()

class StagedTrackingWriterTests(unittest.TestCase):
    def test_write_lock_is_explicit(self):
        self.assertIn('const CLOUD_TRACKING_WRITES_ENABLED=false;', HTML)
    def test_writer_requires_verified_identity(self):
        self.assertIn('const uid=await userId();', HTML)
        self.assertIn('if(!auth)throw Error', HTML)
    def test_writer_never_upserts(self):
        segment = HTML.split('/* Phase 3 staged prediction snapshot cloud writer.')[1]
        self.assertIn("method:'POST'", segment)
        self.assertNotIn("method:'PATCH'", segment)
        self.assertNotIn("method:'DELETE'", segment)
    def test_no_automatic_call(self):
        segment = HTML.split('/* Phase 3 staged prediction snapshot cloud writer.')[1]
        self.assertIn('window.phase3SyncPredictionHistory=sync;', segment)
        self.assertNotIn('phase3SyncPredictionHistory()', segment)

if __name__ == '__main__': unittest.main()
