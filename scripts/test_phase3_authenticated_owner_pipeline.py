import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from phase3_authenticated_owner_pipeline import run

USER = '00000000-0000-4000-8000-000000000001'
EVIDENCE = {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT',
            'authenticated_owner_verified': True, 'database_writes': 0,
            'visible_tracking_records': 0}


class AuthenticatedOwnerPipelineTests(unittest.TestCase):
    def _inputs(self, root):
        a, b = root / 'snapshots.json', root / 'stats.json'
        a.write_text('{}')
        b.write_text('{}')
        return a, b

    def test_missing_inputs_clear_stale_artifacts_without_cloud_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('phase3-owner-tracking-plan.json', 'phase3-grade-export.json'):
                (root / name).write_text('stale')
            def fail(*args, **kwargs):
                raise AssertionError('Cloud must not be called')
            result = run(None, None, root, USER, '', '', '', preflight_fn=fail)
            self.assertFalse(result['ready'])
            self.assertEqual(result['database_writes'], 0)
            self.assertFalse((root / 'phase3-owner-tracking-plan.json').exists())
            self.assertFalse((root / 'phase3-grade-export.json').exists())

    def test_valid_owner_history_is_passed_to_offline_planner(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = self._inputs(root)
            record = {'user_id': USER, 'tracking_id': 'x', 'payload': {'synthetic': True}}
            def read(*args, **kwargs):
                kwargs['record_sink'](record)
                return {**EVIDENCE, 'visible_tracking_records': 1}
            with patch('phase3_authenticated_owner_pipeline.build') as build:
                build.return_value = {'ready': True, 'database_writes': 0, 'proposed_count': 0}
                result = run(a, b, root, USER, 'https://test', 'key', 'token', preflight_fn=read)
                self.assertTrue(result['ready'])
                self.assertFalse(result['cloud_writes_enabled'])
                self.assertEqual(build.call_args.args[3], USER)
            self.assertFalse((root / 'owner-history.json').exists())

    def test_cross_owner_response_rejected_before_planning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = self._inputs(root)
            def read(*args, **kwargs):
                kwargs['record_sink']({'user_id': 'other', 'tracking_id': 'x'})
                return {**EVIDENCE, 'visible_tracking_records': 1}
            with patch('phase3_authenticated_owner_pipeline.build') as build:
                with self.assertRaisesRegex(ValueError, 'another owner'):
                    run(a, b, root, USER, 'https://test', 'key', 'token', preflight_fn=read)
                build.assert_not_called()

    def test_incomplete_preflight_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = self._inputs(root)
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                run(a, b, root, USER, 'https://test', 'key', 'token',
                    preflight_fn=lambda *args, **kwargs: {**EVIDENCE, 'visible_tracking_records': 3})

    def test_wrong_repository_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = self._inputs(root)
            with self.assertRaisesRegex(ValueError, 'TEST repository'):
                run(a, b, root, USER, '', '', '', repository='other/repo',
                    preflight_fn=lambda *args, **kwargs: self.fail('unexpected cloud call'))


if __name__ == '__main__':
    unittest.main()
