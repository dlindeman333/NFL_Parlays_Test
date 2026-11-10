import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from phase3_test_authenticated_grade_runner import execute
from phase3_tracking_live_smoke import BASE, REPOSITORY


class TestAuthenticatedGradeRunner(unittest.TestCase):
    def setUp(self):
        self.env = {'GITHUB_REPOSITORY': REPOSITORY, 'NFL_TEST_SUPABASE_URL': BASE,
                    'NFL_TEST_SUPABASE_PUBLISHABLE_KEY': 'publishable',
                    'NFL_TEST_USER_A_EMAIL': 'a@example.test', 'NFL_TEST_USER_A_PASSWORD': 'secret'}

    def test_no_artifacts_never_logs_in(self):
        login = Mock()
        with self.assertRaisesRegex(ValueError, 'files required'):
            execute('/missing/snapshot', '/missing/stats', '/tmp/out', self.env, login=login)
        login.assert_not_called()

    def test_production_repository_rejected(self):
        env = {**self.env, 'GITHUB_REPOSITORY': 'dlindeman333/NFL_Parlays'}
        with self.assertRaisesRegex(ValueError, 'TEST repository'):
            execute('x', 'y', 'z', env)

    def test_production_supabase_rejected(self):
        env = {**self.env, 'NFL_TEST_SUPABASE_URL': 'https://wpvuunwtyxycqfjwuzkn.supabase.co'}
        with self.assertRaisesRegex(ValueError, 'TEST Supabase'):
            execute('x', 'y', 'z', env)

    def test_authenticated_bridge_passes_owner_without_leaking_token(self):
        with tempfile.TemporaryDirectory() as d:
            snap, stats = Path(d)/'snap.json', Path(d)/'stats.json'
            snap.write_text('{}'); stats.write_text('{}')
            pipeline = Mock(return_value={'database_writes': 0, 'cloud_writes_enabled': False,
                                          'ready': True, 'access_token': 'must-hide'})
            result = execute(snap, stats, d, self.env, login=lambda *args: ('secret-token', 'owner-a'), pipeline=pipeline)
            self.assertNotIn('access_token', result)
            self.assertEqual(pipeline.call_args.args[3:7], ('owner-a', BASE, 'publishable', 'secret-token'))

    def test_refuses_any_write_enabled_result(self):
        with tempfile.TemporaryDirectory() as d:
            snap, stats = Path(d)/'snap.json', Path(d)/'stats.json'
            snap.write_text('{}'); stats.write_text('{}')
            for result in ({'database_writes': 1, 'cloud_writes_enabled': False},
                           {'database_writes': 0, 'cloud_writes_enabled': True}):
                with self.assertRaisesRegex(ValueError, 'cloud writes'):
                    execute(snap, stats, d, self.env, login=lambda *args: ('t', 'u'), pipeline=lambda *args: result)


if __name__ == '__main__':
    unittest.main()
