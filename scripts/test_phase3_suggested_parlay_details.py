import pathlib
import unittest

HTML = pathlib.Path(__file__).resolve().parents[1] / 'index.html'

class SuggestedParlayDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding='utf-8')

    def test_summary_has_leg_level_details(self):
        for marker in ('Suggested ${unique.length}-leg parlay', 'legSummary', 'esc(x.p.n)', 'esc(marketLabel)', 'esc(lineText)', 'esc(x.g.a)', 'esc(x.g.h)'):
            self.assertIn(marker, self.html)

    def test_no_invented_combined_odds(self):
        self.assertIn('combined odds and independence are not assumed', self.html)
        self.assertIn('No verified sportsbook odds', self.html)

    def test_existing_add_control_preserved(self):
        self.assertIn('onclick="advAdd(${i})"', self.html)
        self.assertIn('unique.map(x=>advCard(x,all.indexOf(x)))', self.html)

if __name__ == '__main__':
    unittest.main()
