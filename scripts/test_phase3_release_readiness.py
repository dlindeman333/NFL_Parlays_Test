import tempfile
import unittest
from pathlib import Path
from phase3_release_readiness import assess, CORE_WORKFLOWS, REQUIRED_SCRIPTS


class ReadinessTests(unittest.TestCase):
    def test_real_repository_stays_blocked(self):
        result = assess()
        self.assertFalse(result['ready_for_live_release'])
        self.assertFalse(result['cloud_writes_enabled'])
        self.assertFalse(result['production_authorized'])
        self.assertFalse(result['core_files_missing'])
        self.assertIn('trusted_upstream_publication_timing_unverified', result['release_blockers'])

    def test_missing_core_workflow_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in CORE_WORKFLOWS[1:]:
                p = root / '.github/workflows' / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('name: placeholder\n')
            for name in REQUIRED_SCRIPTS:
                p = root / 'scripts' / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('')
            result = assess(root)
            self.assertIn('.github/workflows/' + CORE_WORKFLOWS[0], result['core_files_missing'])
            self.assertIn('required_release_components_missing', result['release_blockers'])


if __name__ == '__main__':
    unittest.main()
