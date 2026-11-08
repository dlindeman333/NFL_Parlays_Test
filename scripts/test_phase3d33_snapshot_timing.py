import unittest
from phase3d33_snapshot_timing import evaluate
class TimingTests(unittest.TestCase):
    def test_before(self):
        r=evaluate([{'game_id':'a','created_at':'2026-11-08T10:00:00Z','kickoff_at':'2026-11-08T11:00:00Z'}])
        self.assertEqual(r['flagged_count'],0)
    def test_after(self):
        r=evaluate([{'game_id':'a','created_at':'2026-11-08T12:00:00Z','kickoff_at':'2026-11-08T11:00:00Z'}])
        self.assertEqual(r['flagged_count'],1)
    def test_unknown(self):
        self.assertEqual(evaluate([{'game_id':'a'}])['flagged_count'],1)
if __name__=='__main__': unittest.main()
