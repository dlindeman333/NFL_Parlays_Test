"""Prevent read-only service-role audits from accidentally targeting production."""
import os
import unittest
from unittest.mock import patch
from phase3d37j_storage_dry_run import fetch_existing
from phase3d37i_storage_audit import main as audit_main

TEST='https://luxezjthznupdghmexyh.supabase.co'
PROD='https://wpvuunwtyxycqfjwuzkn.supabase.co'
REPO='dlindeman333/NFL_Parlays_Test'

class BoundaryTests(unittest.TestCase):
    def test_storage_rejects_production_before_network(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': REPO, 'SUPABASE_URL': PROD, 'SUPABASE_SERVICE_ROLE_KEY':'fake'}):
            with patch('urllib.request.urlopen') as network:
                with self.assertRaises(ValueError): fetch_existing()
                network.assert_not_called()

    def test_storage_rejects_wrong_repository_before_network(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'dlindeman333/NFL_Parlays', 'SUPABASE_URL': TEST, 'SUPABASE_SERVICE_ROLE_KEY':'fake'}):
            with patch('urllib.request.urlopen') as network:
                with self.assertRaises(ValueError): fetch_existing()
                network.assert_not_called()

    def test_audit_rejects_production_before_network(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': REPO, 'SUPABASE_URL': PROD, 'SUPABASE_SERVICE_ROLE_KEY':'fake'}):
            with patch('urllib.request.urlopen') as network:
                self.assertEqual(audit_main(), 2)
                network.assert_not_called()

    def test_audit_rejects_wrong_repository_before_network(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'other/repo', 'SUPABASE_URL': TEST, 'SUPABASE_SERVICE_ROLE_KEY':'fake'}):
            with patch('urllib.request.urlopen') as network:
                self.assertEqual(audit_main(), 2)
                network.assert_not_called()

if __name__=='__main__': unittest.main()
