import tempfile
import unittest
from pathlib import Path
from phase3_release_static_check import check

class StaticReleaseTests(unittest.TestCase):
    def test_current_application(self):
        result = check()
        self.assertGreater(result['inline_scripts_checked'], 0)
        self.assertEqual(result['cloud_writes_performed'], 0)
    def test_missing_page_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                check(Path(d))
    def test_invalid_javascript_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'index.html').write_text('<script>const = ;</script>')
            with self.assertRaises(RuntimeError):
                check(Path(d))

if __name__ == '__main__': unittest.main()
