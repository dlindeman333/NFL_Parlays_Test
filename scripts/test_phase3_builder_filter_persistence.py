"""Regression contracts for the browser's remembered builder filters."""
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / 'index.html').read_text()


class BuilderFilterPersistenceTests(unittest.TestCase):
    def test_reset_button_is_available(self):
        self.assertIn('id="resetBuilderFilters"', HTML)
        self.assertIn('onclick="resetBuilderFilters()"', HTML)

    def test_filter_values_are_allowlisted(self):
        self.assertIn('TF.some(x=>x[0]===rememberedBuilderFilters.tf)', HTML)
        self.assertIn('PF.some(x=>x[0]===rememberedBuilderFilters.pf)', HTML)

    def test_reset_clears_filters_and_search(self):
        start = HTML.index('function resetBuilderFilters()')
        body = HTML[start:HTML.index('function drawF()', start)]
        for expected in ['tf="all"', 'pf="all"', 'gameQuery=""', 'search.value=""', 'saveBuilderFilters()']:
            self.assertIn(expected, body)

    def test_search_updates_saved_filters(self):
        self.assertIn('gameQuery=e.target.value.trim().toLowerCase().slice(0,120);saveBuilderFilters();draw()', HTML)


if __name__ == '__main__':
    unittest.main()
