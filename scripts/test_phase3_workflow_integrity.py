import tempfile
import unittest
from pathlib import Path
from phase3_workflow_integrity import audit

class WorkflowIntegrityTests(unittest.TestCase):
    def test_detects_missing_entrypoint(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'.github/workflows').mkdir(parents=True)
            (root/'scripts').mkdir()
            (root/'.github/workflows/a.yml').write_text('run: python scripts/missing.py\n')
            result=audit(root)
            self.assertEqual(result['missing_count'], 1)
            self.assertEqual(result['missing'][0]['script'], 'scripts/missing.py')
    def test_present_entrypoint(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'.github/workflows').mkdir(parents=True)
            (root/'scripts').mkdir()
            (root/'scripts/exists.py').write_text('pass\n')
            (root/'.github/workflows/a.yml').write_text('run: python scripts/exists.py\n')
            self.assertEqual(audit(root)['missing_count'], 0)

if __name__=='__main__': unittest.main()
