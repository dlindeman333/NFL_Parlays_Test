import csv
import json
import tempfile
import unittest
from pathlib import Path
from phase3_postgame_grading_gate import run


class GateTests(unittest.TestCase):
    def test_label_without_timestamps_is_rejected(self):
        from phase3_postgame_grading_gate import validate_snapshot
        self.assertIn('timestamps', validate_snapshot({'provenance_status': 'VERIFIED_PREGAME', 'picks': [{}]}))

    def test_after_kickoff_is_rejected(self):
        from phase3_postgame_grading_gate import validate_snapshot
        self.assertIn('before kickoff', validate_snapshot({'provenance_status': 'VERIFIED_PREGAME', 'captured_at': '2026-11-01T19:00:00Z', 'kickoff_at': '2026-11-01T18:00:00Z', 'picks': [{}]}))

    def test_naive_timestamps_rejected(self):
        from phase3_postgame_grading_gate import validate_snapshot
        self.assertIn('timezone-aware', validate_snapshot({'provenance_status': 'VERIFIED_PREGAME', 'captured_at': '2026-11-01T16:00:00', 'kickoff_at': '2026-11-01T18:00:00', 'picks': [{}]}))

    def test_valid_timestamp_order_accepted(self):
        from phase3_postgame_grading_gate import validate_snapshot
        self.assertIsNone(validate_snapshot({'provenance_status': 'VERIFIED_PREGAME', 'captured_at': '2026-11-01T12:00:00-04:00', 'kickoff_at': '2026-11-01T18:00:00Z', 'picks': [{}]}))

    def test_missing_inputs_fail_closed(self):
        r = run()
        self.assertFalse(r['ready'])
        self.assertEqual(r['database_writes'], 0)

    def test_unverified_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'s.json').write_text(json.dumps([{'season': 2026, 'week': 9, 'game_id': 'x', 'picks': []}]))
            (p/'stats.csv').write_text('season,week\n2026,9\n')
            r = run(p/'s.json', p/'stats.csv')
            self.assertFalse(r['ready'])
            self.assertEqual(r['grades_persisted'], 0)

    def test_verified_preview_no_writes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'s.json').write_text(json.dumps([{'season': 2026, 'week': 9, 'game_id': 'x', 'provenance_status': 'VERIFIED_PREGAME', 'captured_at': '2026-11-01T16:00:00Z', 'kickoff_at': '2026-11-01T18:00:00Z', 'picks': [{'market': 'player', 'stat': 'rec_yards', 'side': 'o', 'line': 49.5, 'player_name': 'Sample Player', 'team': 'BUF'}]}]))
            with (p/'stats.csv').open('w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=['season','week','game_id','name','team','game_status','rec_yards'])
                w.writeheader()
                w.writerow({'season': 2026, 'week': 9, 'game_id': 'x', 'name': 'Sample Player', 'team': 'BUF', 'game_status': 'COMPLETED', 'rec_yards': 67})
            r = run(p/'s.json', p/'stats.csv')
            self.assertTrue(r['ready'])
            self.assertEqual(r['preview']['summary']['HIT'], 1)
            self.assertEqual(r['database_writes'], 0)


if __name__ == '__main__':
    unittest.main()

class CompletenessTests(unittest.TestCase):
    def setUp(self):
        self.snap = {'season': 2026, 'week': 10, 'game_id': 'sample-game', 'provenance_status': 'VERIFIED_PREGAME', 'captured_at': '2026-11-01T16:00:00Z', 'kickoff_at': '2026-11-01T18:00:00Z', 'picks': [{'market': 'player', 'stat': 'rec_yards', 'side': 'o', 'line': 49.5, 'player_name': 'Sample Player', 'team': 'BUF'}]}
        self.stats = 'season,week,game_id,name,team,game_status,rec_yards\n2026,10,sample-game,Sample Player,BUF,COMPLETED,67\n'

    def check(self, snaps, stats=None):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'snaps.json').write_text(json.dumps(snaps))
            (p/'stats.csv').write_text(self.stats if stats is None else stats)
            return run(p/'snaps.json', p/'stats.csv')

    def test_duplicate_game_rejected(self):
        result = self.check([self.snap, dict(self.snap)])
        self.assertFalse(result['ready'])
        self.assertIn('Duplicate', result['reason'])

    def test_missing_game_identity_rejected(self):
        result = self.check([{**self.snap, 'game_id': ''}])
        self.assertFalse(result['ready'])
        self.assertIn('identity', result['reason'])

    def test_empty_stats_rejected(self):
        result = self.check([self.snap], 'season,week,game_id,name,team,game_status,rec_yards\n')
        self.assertFalse(result['ready'])
        self.assertIn('empty', result['reason'])

    def test_all_unavailable_rejected(self):
        result = self.check([self.snap], 'season,week,game_id,name,team,game_status,rec_yards\n2026,10,sample-game,Sample Player,BUF,SCHEDULED,67\n')
        self.assertFalse(result['ready'])
        self.assertEqual(result['preview']['summary']['UNAVAILABLE'], 1)

    def test_partially_unavailable_batch_is_not_ready(self):
        second = dict(self.snap)
        second['game_id'] = 'second-game'
        second['picks'] = [{**self.snap['picks'][0], 'player_name': 'Missing Player'}]
        result = self.check([self.snap, second])
        self.assertFalse(result['ready'])
        self.assertEqual(result['preview']['summary']['HIT'], 1)
        self.assertEqual(result['preview']['summary']['UNAVAILABLE'], 1)
        self.assertIn('lack completed', result['reason'])
        self.assertEqual(result['grades_persisted'], 0)

    def test_completed_stats_allow_preview(self):
        result = self.check([self.snap])
        self.assertTrue(result['ready'])
        self.assertEqual(result['preview']['summary']['HIT'], 1)
        self.assertEqual(result['database_writes'], 0)
