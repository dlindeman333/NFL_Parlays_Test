from pathlib import Path
import unittest

class CompletedResultsUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(Path(__file__).resolve().parents[1]/'index.html').read_text()
    def test_disagreement_panel_removed(self):
        self.assertNotIn('Where the model disagrees with the feed',self.html)
    def test_completed_results_grouped_by_market(self):
        for marker in ('Potential Plays results by bet type','Moneyline','Team props','Player props','hits ·','misses ·','Ungraded'):
            self.assertIn(marker,self.html)
    def test_retrospective_disclaimer(self):
        self.assertIn('not verified pregame picks',self.html)

if __name__=='__main__': unittest.main()
