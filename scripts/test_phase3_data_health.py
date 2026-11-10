import pathlib
import unittest

HTML = pathlib.Path(__file__).resolve().parents[1] / 'index.html'

class DataHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding='utf-8')

    def test_status_panel_and_manual_refresh(self):
        for marker in ('id="phase3DataHealth"', 'id="phase3HealthResults"', 'id="phase3HealthRefresh"', "refresh.addEventListener('click',update)"):
            self.assertIn(marker, self.html)

    def test_diagnostics_are_read_only_and_candid(self):
        for marker in ('server reachability unverified', 'Cloud writes', 'Paused for Phase 3 TEST validation', 'do not certify that NFL feeds are current'):
            self.assertIn(marker, self.html)

if __name__ == '__main__':
    unittest.main()
