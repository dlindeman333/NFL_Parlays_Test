import pathlib
import re
import unittest

HTML = pathlib.Path(__file__).resolve().parents[1].joinpath('index.html').read_text()

class PrebetWarningTests(unittest.TestCase):
    def test_validator_is_present(self):
        self.assertIn('function validateDraftForBet(', HTML)
    def test_warnings_are_rendered_without_html_interpolation(self):
        self.assertIn("item.textContent=warning", HTML)
        self.assertIn("panel.setAttribute('role','status')", HTML)
    def test_existing_draw_calls_validator(self):
        self.assertIn('validateDraftForBet(legs,games,N,mode)', HTML)
    def test_detects_duplicates_opposing_and_completed(self):
        for phrase in ('same selection appears more than once', 'Opposing sides of the same market', 'already completed'):
            self.assertIn(phrase, HTML)
    def test_includes_live_line_disclaimer(self):
        self.assertIn('not live sportsbook quotes', HTML)

if __name__ == '__main__': unittest.main()
