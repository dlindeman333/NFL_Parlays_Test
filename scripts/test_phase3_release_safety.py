from pathlib import Path
import unittest

HTML = Path(__file__).resolve().parents[1].joinpath('index.html').read_text()

class ReleaseSafetyTests(unittest.TestCase):
    def test_my_parlays_only_requested_metrics(self):
        summary = HTML.split('$("sumry").innerHTML=`',1)[1].split('`;',1)[0]
        self.assertIn('Open parlays',summary)
        self.assertIn('Overall record',summary)
        self.assertNotIn('Net P/L',summary)
        self.assertNotIn('ROI',summary)
    def test_snapshots_require_known_future_kickoff(self):
        self.assertIn("Number.isFinite(kickoff) && kickoff>now.getTime()",HTML)
        self.assertNotIn("!x.g.date || Number.isNaN(Date.parse(x.g.date))",HTML)
    def test_cloud_writes_still_locked(self):
        self.assertIn('const CLOUD_TRACKING_WRITES_ENABLED=false;',HTML)

if __name__=='__main__': unittest.main()
