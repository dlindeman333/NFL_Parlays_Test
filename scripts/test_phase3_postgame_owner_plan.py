import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from phase3_postgame_owner_plan import build

USER = '00000000-0000-4000-8000-000000000001'
ROW = {'tracking_id': 'a' * 64, 'grade': 'HIT', 'provenance_status': 'VERIFIED_PREGAME'}

class TestOwnerPlan(unittest.TestCase):
    def test_missing_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            result = build(None, None, 'unused', USER, d)
            self.assertFalse(result['ready'])
            self.assertEqual(result['database_writes'], 0)
            self.assertFalse((Path(d) / 'phase3-owner-tracking-plan.json').exists())

    def test_failed_rerun_removes_previous_owner_plan(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / 'phase3-owner-tracking-plan.json'
            old.write_text('{"stale": true}')
            result = build(None, None, 'unused', USER, d)
            self.assertFalse(result['ready'])
            self.assertFalse(old.exists())

    def test_conflicting_rerun_removes_previous_owner_plan(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / 'phase3-owner-tracking-plan.json'
            old.write_text('{"stale": true}')
            existing = Path(d) / 'existing.json'
            existing.write_text(json.dumps([{'user_id': USER, 'tracking_id': 'a'*64, 'payload': {'grade': 'MISS'}}]))
            with patch('phase3_postgame_owner_plan.produce', return_value={'ready': True}):
                (Path(d) / 'phase3-grade-export.json').write_text(json.dumps({
                    'mode': 'OFFLINE_GRADE_EXPORT', 'ready': True,
                    'database_writes': 0, 'rows': [ROW]}))
                result = build('a', 'b', existing, USER, d)
            self.assertFalse(result['ready'])
            self.assertFalse(old.exists())

    def test_conflicting_owner_plan_invalidates_grade_export(self):
        with tempfile.TemporaryDirectory() as d:
            existing = Path(d) / 'existing.json'
            existing.write_text(json.dumps([{'user_id': USER, 'tracking_id': 'a'*64,
                                             'payload': {'grade': 'MISS'}}]))
            grade_path = Path(d) / 'phase3-grade-export.json'
            with patch('phase3_postgame_owner_plan.produce', return_value={'ready': True}):
                grade_path.write_text(json.dumps({'mode': 'OFFLINE_GRADE_EXPORT',
                    'ready': True, 'database_writes': 0, 'rows': [ROW]}))
                result = build('a', 'b', existing, USER, d)
            self.assertFalse(result['ready'])
            self.assertFalse(grade_path.exists())

    def test_invalid_existing_records_invalidate_grade_export(self):
        with tempfile.TemporaryDirectory() as d:
            existing = Path(d) / 'existing.json'
            existing.write_text('{invalid json')
            grade_path = Path(d) / 'phase3-grade-export.json'
            with patch('phase3_postgame_owner_plan.produce', return_value={'ready': True}):
                grade_path.write_text(json.dumps({'mode': 'OFFLINE_GRADE_EXPORT',
                    'ready': True, 'database_writes': 0, 'rows': [ROW]}))
                with self.assertRaises(json.JSONDecodeError):
                    build('a', 'b', existing, USER, d)
            self.assertFalse(grade_path.exists())
            self.assertFalse((Path(d) / 'phase3-owner-tracking-plan.json').exists())

    def test_valid_offline_export_produces_locked_owner_plan(self):
        with tempfile.TemporaryDirectory() as d:
            existing = Path(d) / 'existing.json'
            existing.write_text('[]')
            with patch('phase3_postgame_owner_plan.produce', return_value={'ready': True}):
                (Path(d) / 'phase3-grade-export.json').write_text(json.dumps({
                    'mode': 'OFFLINE_GRADE_EXPORT', 'ready': True,
                    'database_writes': 0, 'rows': [ROW]}))
                result = build('a', 'b', existing, USER, d)
            self.assertTrue(result['ready'])
            self.assertEqual(result['proposed_count'], 1)
            self.assertEqual(result['database_writes'], 0)
            plan = json.loads((Path(d) / 'phase3-owner-tracking-plan.json').read_text())
            self.assertFalse(plan['activation_allowed'])
            self.assertEqual(plan['proposed_inserts'][0]['user_id'], USER)

    def test_conflicting_existing_grade_blocks_plan(self):
        with tempfile.TemporaryDirectory() as d:
            existing = Path(d) / 'existing.json'
            existing.write_text(json.dumps([{'user_id': USER, 'tracking_id': 'a'*64, 'payload': {'grade': 'MISS'}}]))
            with patch('phase3_postgame_owner_plan.produce', return_value={'ready': True}):
                (Path(d) / 'phase3-grade-export.json').write_text(json.dumps({
                    'mode': 'OFFLINE_GRADE_EXPORT', 'ready': True,
                    'database_writes': 0, 'rows': [ROW]}))
                result = build('a', 'b', existing, USER, d)
            self.assertFalse(result['ready'])
            self.assertFalse((Path(d) / 'phase3-owner-tracking-plan.json').exists())

if __name__ == '__main__':
    unittest.main()
