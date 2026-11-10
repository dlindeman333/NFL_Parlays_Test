import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / '.github/workflows/nfl-phase3-prediction-capture-link-readonly.yml'

class WorkflowIntegrationTests(unittest.TestCase):
    def test_pipeline_order(self):
        text = WORKFLOW.read_text()
        commands = ['scripts/phase3d37e_capture.py --season',
                    'scripts/phase3d37e_capture.py --verify',
                    'scripts/phase3d37f_pregame.py --season',
                    'scripts/phase3_prediction_capture_link.py --capture-dir']
        positions = [text.index(command) for command in commands]
        self.assertEqual(positions, sorted(positions))

    def test_read_only_and_fail_closed(self):
        text = WORKFLOW.read_text()
        self.assertIn('contents: read', text)
        self.assertIn("result['linkage']!='PASS'", text)
        self.assertIn('phase3-evidence/capture_manifest.json', text)
        self.assertNotIn('phase3-evidence/source_stats.csv', text)
        self.assertNotIn('git push', text)

if __name__ == '__main__': unittest.main()
