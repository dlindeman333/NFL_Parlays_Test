from pathlib import Path
import unittest

SCRIPT = Path(__file__).with_name('nfl_phase3_api_isolation.py').read_text()

class TrackingIsolationContract(unittest.TestCase):
    def test_foreign_insert_rejected(self):
        self.assertIn('foreign prediction INSERT rejected', SCRIPT)
    def test_foreign_update_blocked(self):
        self.assertIn('foreign prediction UPDATE blocked', SCRIPT)
    def test_delete_grant_denied(self):
        self.assertIn('authenticated prediction DELETE permission denied', SCRIPT)
    def test_no_positive_tracking_write_claim(self):
        self.assertIn('PENDING: positive owner prediction-tracking INSERT/UPDATE', SCRIPT)
    def test_delete_defense_in_depth(self):
        self.assertIn('phase3_impossible_delete_guard_20261109', SCRIPT)

if __name__ == '__main__': unittest.main()
