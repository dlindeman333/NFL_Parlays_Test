import unittest
from unittest.mock import patch
from phase3_tracking_write_adapter import reconcile_after_failure
from test_phase3_tracking_write_adapter import sample, OWNER

EVIDENCE = {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT',
            'authenticated_owner_verified': True, 'database_writes': 0,
            'visible_tracking_records': 1}

class TestReconciliation(unittest.TestCase):
    def test_exact_match_is_confirmed_without_writes(self):
        row = sample()['proposed_inserts'][0]
        def fake(*args, **kwargs):
            kwargs['record_sink'](row.copy())
            return EVIDENCE
        with patch('phase3_tracking_write_adapter.preflight', side_effect=fake):
            result = reconcile_after_failure(sample(), OWNER, '', '', '', '')
        self.assertEqual(result['confirmed_ids'], [row['tracking_id']])
        self.assertEqual(result['database_writes'], 0)
        self.assertFalse(result['safe_to_retry_automatically'])

    def test_missing_record_requires_new_plan(self):
        with patch('phase3_tracking_write_adapter.preflight', return_value={**EVIDENCE, 'visible_tracking_records': 0}):
            result = reconcile_after_failure(sample(), OWNER, '', '', '', '')
        self.assertEqual(len(result['missing_ids']), 1)
        self.assertFalse(result['safe_to_retry_automatically'])

    def test_conflicting_payload_is_not_confirmed(self):
        row = sample()['proposed_inserts'][0].copy()
        row['payload'] = {'grade': 'MISS', 'provenance_status': 'VERIFIED_PREGAME'}
        def fake(*args, **kwargs):
            kwargs['record_sink'](row)
            return EVIDENCE
        with patch('phase3_tracking_write_adapter.preflight', side_effect=fake):
            result = reconcile_after_failure(sample(), OWNER, '', '', '', '')
        self.assertEqual(result['conflicting_ids'], [row['tracking_id']])

    def test_unverified_preflight_is_rejected(self):
        with patch('phase3_tracking_write_adapter.preflight', return_value={'database_writes': 0}):
            with self.assertRaisesRegex(ValueError, 'evidence'):
                reconcile_after_failure(sample(), OWNER, '', '', '', '')

if __name__ == '__main__':
    unittest.main()
