import json
import tempfile
import unittest
from pathlib import Path
from phase3_grade_export import build_export


class GradeExportTests(unittest.TestCase):
    def setUp(self):
        self.snap = {'season': 2026, 'week': 10, 'game_id': 'sample-game',
                     'provenance_status': 'VERIFIED_PREGAME',
                     'captured_at': '2026-11-01T16:00:00Z',
                     'kickoff_at': '2026-11-01T18:00:00Z',
                     'picks': [{'market': 'player', 'stat': 'rec_yards', 'side': 'o',
                                'line': 49.5, 'player_name': 'Sample Player', 'team': 'BUF'}]}
        self.stats = 'season,week,game_id,name,team,game_status,rec_yards\n2026,10,sample-game,Sample Player,BUF,COMPLETED,67\n'

    def evaluate(self, snap, stats=None):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'snap.json').write_text(json.dumps([snap]))
            (p/'stats.csv').write_text(self.stats if stats is None else stats)
            return build_export(p/'snap.json', p/'stats.csv')

    def test_ready_export_is_deterministic_and_read_only(self):
        a, b = self.evaluate(self.snap), self.evaluate(self.snap)
        self.assertEqual(a, b)
        self.assertTrue(a['ready'])
        self.assertEqual(a['database_writes'], 0)
        self.assertEqual(a['rows'][0]['grade'], 'HIT')
        self.assertEqual(len(a['rows'][0]['tracking_id']), 64)

    def test_unverified_snapshots_are_blocked(self):
        result = self.evaluate({**self.snap, 'provenance_status': 'UNVERIFIED'})
        self.assertFalse(result['ready'])
        self.assertEqual(result['rows'], [])

    def test_incomplete_stats_block_export(self):
        result = self.evaluate(self.snap, self.stats.replace('COMPLETED', 'SCHEDULED'))
        self.assertFalse(result['ready'])
        self.assertEqual(result['rows'], [])

    def test_changed_pick_changes_tracking_identity(self):
        a = self.evaluate(self.snap)
        altered = {**self.snap, 'picks': [{**self.snap['picks'][0], 'line': 55.5}]}
        b = self.evaluate(altered)
        self.assertNotEqual(a['rows'][0]['tracking_id'], b['rows'][0]['tracking_id'])


if __name__ == '__main__':
    unittest.main()
