"""Regression checks for TEST-only refresh/capture workflow safety."""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/nfl-phase3-test-refresh-capture.yml'

class TestRefreshCaptureWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding='utf-8')

    def test_repository_pinned(self):
        self.assertIn("github.repository == 'dlindeman333/NFL_Parlays_Test'", self.source)
        self.assertIn('python scripts/phase3_test_boundary.py', self.source)

    def test_upload_only_scheduled_or_manual_explicit_opt_in(self):
        self.assertIn("github.event_name == 'schedule' || (github.event_name == 'workflow_dispatch' && inputs.authorize_test_stats_upload == true)", self.source)
        self.assertEqual(self.source.count("github.event_name == 'schedule' ||"), 3)
        self.assertIn('--upload', self.source)
        self.assertEqual(self.source.count('--upload'), 1)

    def test_export_cannot_write_by_inherited_credentials(self):
        self.assertIn("SUPABASE_URL: ''", self.source)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY: ''", self.source)

    def test_upload_requires_validation_and_test_boundary(self):
        self.assertLess(self.source.index('Validate export without writing'), self.source.index('Guarded TEST-only stats upload'))
        self.assertLess(self.source.index('Verify repository and TEST target'), self.source.index('Guarded TEST-only stats upload'))
        self.assertIn('python scripts/phase3_test_stats_upload.py --csv nfl_player_stats.csv --season "$NFL_SEASON" --upload', self.source)

    def test_capture_integrity_precedes_artifact_publication(self):
        self.assertLess(self.source.index("Verify captured forecast integrity before publication"), self.source.index("Preserve read-only evidence"))
        self.assertIn("python scripts/phase3_capture_artifact_check.py", self.source)

    def test_no_prediction_cloud_writes(self):
        self.assertNotIn('phase3_tracking_write_adapter.py', self.source)
        self.assertIn('actions/upload-artifact@v4', self.source)

if __name__ == '__main__':
    unittest.main()
