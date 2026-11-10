from pathlib import Path
import unittest

HTML = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")

class AdvancedDetailsTests(unittest.TestCase):
    def test_methodology_is_collapsible_and_closed_by_default(self):
        self.assertIn('<details id="phase3AdvancedMethodology"', HTML)
        opening = HTML.split('<details id="phase3AdvancedMethodology"', 1)[1].split('>', 1)[0]
        self.assertNotIn(' open', opening)
        self.assertIn('How matchup analysis works (advanced details)', HTML)

    def test_disclosure_preserves_limitations_and_recommendation_panel(self):
        section = HTML.split('<details id="phase3AdvancedMethodology"', 1)[1].split('</details>', 1)[0]
        self.assertIn('Not a live generative AI service', section)
        self.assertIn('not sportsbook odds', section)
        self.assertIn('id="advRecommendationPanel"', HTML)
        self.assertIn('id="advPerformancePanel"', HTML)

if __name__ == "__main__":
    unittest.main()
