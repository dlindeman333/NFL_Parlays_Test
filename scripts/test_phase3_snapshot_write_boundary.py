import unittest
from phase3_snapshot_write_boundary import require_snapshot_write_authorization

class TestLegacySnapshotWriteBoundary(unittest.TestCase):
    def test_production_rejected(self):
        with self.assertRaisesRegex(PermissionError, 'boundary mismatch'):
            require_snapshot_write_authorization({'GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays','SUPABASE_URL':'https://wpvuunwtyxycqfjwuzkn.supabase.co'})
    def test_test_environment_still_locked(self):
        with self.assertRaisesRegex(PermissionError, 'Legacy snapshot writer disabled'):
            require_snapshot_write_authorization({'GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays_Test','SUPABASE_URL':'https://luxezjthznupdghmexyh.supabase.co'})
    def test_host_spoofing_rejected(self):
        with self.assertRaisesRegex(PermissionError, 'boundary mismatch'):
            require_snapshot_write_authorization({'GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays_Test','SUPABASE_URL':'https://luxezjthznupdghmexyh.supabase.co.evil.com'})
