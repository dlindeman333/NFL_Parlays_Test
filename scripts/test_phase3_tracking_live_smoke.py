import unittest
from unittest.mock import patch
import phase3_tracking_live_smoke as smoke

class LiveSmokeTests(unittest.TestCase):
    def test_rejects_production_repo_before_login(self):
        with patch.object(smoke, 'authenticate') as auth:
            with self.assertRaises(ValueError):
                smoke.run({'GITHUB_REPOSITORY': 'dlindeman333/NFL_Parlays', 'NFL_TEST_SUPABASE_URL': smoke.BASE})
            auth.assert_not_called()

    def test_rejects_production_database_before_login(self):
        with patch.object(smoke, 'authenticate') as auth:
            with self.assertRaises(ValueError):
                smoke.run({'GITHUB_REPOSITORY': smoke.REPOSITORY, 'NFL_TEST_SUPABASE_URL': 'https://wpvuunwtyxycqfjwuzkn.supabase.co'})
            auth.assert_not_called()

    def test_two_distinct_users_read_only(self):
        env = {'GITHUB_REPOSITORY': smoke.REPOSITORY, 'NFL_TEST_SUPABASE_URL': smoke.BASE,
               'NFL_TEST_SUPABASE_PUBLISHABLE_KEY': 'key', 'NFL_TEST_USER_A_EMAIL': 'a',
               'NFL_TEST_USER_A_PASSWORD': 'a-pass', 'NFL_TEST_USER_B_EMAIL': 'b',
               'NFL_TEST_USER_B_PASSWORD': 'b-pass'}
        with patch.object(smoke, 'verify_cross_owner_denied', return_value=True) as cross, \
             patch.object(smoke, 'authenticate', side_effect=[('token-a','owner-a'), ('token-b','owner-b')]) as auth, \
             patch.object(smoke, 'preflight', side_effect=[{'authenticated_owner_verified':True,'database_writes':0,'visible_tracking_records':1}, {'authenticated_owner_verified':True,'database_writes':0,'visible_tracking_records':0}]) as pre:
            result = smoke.run(env)
        self.assertEqual(result['database_writes'], 0)
        self.assertEqual(pre.call_count, 2)
        self.assertEqual(auth.call_count, 2)
        self.assertEqual(cross.call_count, 2)
        self.assertEqual(result['rls_evidence'], 'PARTIAL_READ_ONLY_EVIDENCE')
        self.assertFalse(result['write_isolation_verified'])

    def test_empty_histories_are_inconclusive(self):
        env = {'GITHUB_REPOSITORY': smoke.REPOSITORY, 'NFL_TEST_SUPABASE_URL': smoke.BASE}
        with patch.object(smoke, 'verify_cross_owner_denied', return_value=True), \
             patch.object(smoke, 'authenticate', side_effect=[('token-a','owner-a'), ('token-b','owner-b')]), \
             patch.object(smoke, 'preflight', return_value={'authenticated_owner_verified': True, 'database_writes': 0, 'visible_tracking_records': 0}):
            result = smoke.run(env)
        self.assertEqual(result['rls_evidence'], 'INCONCLUSIVE_EMPTY_HISTORIES')
        self.assertFalse(result['write_isolation_verified'])

    def test_same_owner_fails(self):
        env = {'GITHUB_REPOSITORY': smoke.REPOSITORY, 'NFL_TEST_SUPABASE_URL': smoke.BASE}
        with patch.object(smoke, 'authenticate', return_value=('token','owner')), \
             patch.object(smoke, 'preflight', return_value={'authenticated_owner_verified':True,'database_writes':0,'visible_tracking_records':0}):
            with self.assertRaises(ValueError):
                smoke.run(env)

    def test_preflight_write_claim_rejected(self):
        env = {'GITHUB_REPOSITORY': smoke.REPOSITORY, 'NFL_TEST_SUPABASE_URL': smoke.BASE}
        with patch.object(smoke, 'authenticate', return_value=('token','owner')), \
             patch.object(smoke, 'preflight', return_value={'authenticated_owner_verified':True,'database_writes':1,'visible_tracking_records':0}):
            with self.assertRaises(ValueError):
                smoke.run(env)

    def test_cross_owner_empty_response(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'[]'
        requests = []
        def opener(req, timeout):
            requests.append(req)
            return Response()
        self.assertTrue(smoke.verify_cross_owner_denied('key', 'token', 'other', opener))
        self.assertEqual(requests[0].get_method(), 'GET')
        self.assertIn('user_id=eq.other', requests[0].full_url)

    def test_cross_owner_leak_rejected(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'[{"tracking_id":"secret"}]'
        with self.assertRaisesRegex(ValueError, 'RLS isolation failed'):
            smoke.verify_cross_owner_denied('key', 'token', 'other', lambda *a, **k: Response())

if __name__ == '__main__':
    unittest.main()
