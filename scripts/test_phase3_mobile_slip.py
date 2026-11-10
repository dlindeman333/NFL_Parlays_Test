import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'index.html').read_text(encoding='utf-8')

class MobileSlipTests(unittest.TestCase):
    def test_dialog_and_controls_exist(self):
        for item in ('id="phase3MobileSlipToggle"', 'id="phase3MobileSlipDialog"', 'id="phase3MobileSlipClose"', 'aria-expanded="false"'):
            self.assertIn(item, HTML)
    def test_moves_original_elements_not_clones(self):
        self.assertIn('content.appendChild(node)', HTML)
        self.assertIn('parent.insertBefore(node,', HTML)
        self.assertIn("dialog.addEventListener('close'", HTML)
    def test_desktop_responsive_closes_drawer(self):
        self.assertIn("matchMedia('(min-width:701px)')", HTML)
        self.assertIn('env(safe-area-inset-bottom)', HTML)

if __name__ == '__main__': unittest.main()
