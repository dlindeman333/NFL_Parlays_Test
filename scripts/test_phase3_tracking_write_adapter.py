import hashlib
import unittest
from unittest.mock import patch
from phase3_tracking_write_adapter import apply_plan, prepare_write, PartialTrackingWriteError
from phase3_tracking_persistence_plan import _canonical

OWNER = '11111111-1111-4111-8111-111111111111'

def sample():
    rows = [{'user_id': OWNER, 'tracking_id': 'a' * 64,
             'payload': {'provenance_status': 'VERIFIED_PREGAME', 'grade': 'HIT'}}]
    return {'mode': 'TRACKING_PERSISTENCE_PLAN_ONLY', 'database_writes': 0,
            'activation_allowed': False, 'conflicts_blocked': [],
            'proposed_inserts': rows,
            'proposal_sha256': hashlib.sha256(_canonical(rows).encode()).hexdigest()}

class TestWriteAdapter(unittest.TestCase):
    def test_default_locked_without_network(self):
        with patch('phase3_tracking_write_adapter.preflight') as check:
            result = apply_plan(sample(), OWNER, '', '', '', '', enabled=False)
            self.assertEqual(result['database_writes'], 0)
            check.assert_not_called()

    def test_rejects_modified_plan(self):
        data = sample()
        data['proposed_inserts'][0]['payload']['grade'] = 'MISS'
        with self.assertRaisesRegex(ValueError, 'integrity'):
            prepare_write(data, OWNER)

    def test_rejects_wrong_owner(self):
        with self.assertRaisesRegex(ValueError, 'owner'):
            prepare_write(sample(), '22222222-2222-4222-8222-222222222222')

    def test_rejects_conflicts(self):
        data = sample()
        data['conflicts_blocked'] = ['a' * 64]
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            prepare_write(data, OWNER)

    def test_rejects_unverified_payload(self):
        data = sample()
        data['proposed_inserts'][0]['payload']['provenance_status'] = 'UNVERIFIED'
        data['proposal_sha256'] = hashlib.sha256(_canonical(data['proposed_inserts']).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'Unverified'):
            prepare_write(data, OWNER)

    def test_synthetic_security_payload_rejected_even_with_valid_hash(self):
        for flag in ({'synthetic': True}, {'exclude_from_grading': True},
                     {'exclude_from_accuracy': True}, {'record_type': 'RLS_SECURITY_TEST'}):
            with self.subTest(flag=flag):
                data = sample()
                data['proposed_inserts'][0]['payload'].update(flag)
                data['proposal_sha256'] = hashlib.sha256(_canonical(data['proposed_inserts']).encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, 'Unverified'):
                    prepare_write(data, OWNER)

    def test_stale_plan_rejected_before_any_post(self):
        def fake_preflight(*args, **kwargs):
            kwargs['record_sink']({'tracking_id': 'a' * 64})
            return {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT', 'authenticated_owner_verified': True, 'database_writes': 0, 'visible_tracking_records': 1}
        with patch('phase3_tracking_write_adapter.preflight', side_effect=fake_preflight):
            with self.assertRaisesRegex(ValueError, 'stale'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected POST'))

    def test_preflight_failure_prevents_post(self):
        with patch('phase3_tracking_write_adapter.preflight', side_effect=ValueError('invalid token')):
            with self.assertRaisesRegex(ValueError, 'invalid token'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected POST'))

    def test_rejects_preflight_without_verified_evidence(self):
        with patch('phase3_tracking_write_adapter.preflight', return_value={'authenticated_owner_verified': True}):
            with self.assertRaisesRegex(ValueError, 'evidence'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected POST'))

    def test_rejects_preflight_with_reported_writes(self):
        result = {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT',
                  'authenticated_owner_verified': True, 'database_writes': 1,
                  'visible_tracking_records': 0}
        with patch('phase3_tracking_write_adapter.preflight', return_value=result):
            with self.assertRaisesRegex(ValueError, 'evidence'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected POST'))

    def test_empty_batch_never_uses_network(self):
        data = sample()
        data['proposed_inserts'] = []
        data['proposal_sha256'] = hashlib.sha256(_canonical([]).encode()).hexdigest()
        with patch('phase3_tracking_write_adapter.preflight') as check:
            result = apply_plan(data, OWNER, '', '', '', '', enabled=True)
            self.assertEqual(result['database_writes'], 0)
            check.assert_not_called()

    def test_rejects_preflight_without_verified_evidence(self):
        with patch('phase3_tracking_write_adapter.preflight', return_value={'authenticated_owner_verified': True}):
            with self.assertRaisesRegex(ValueError, 'evidence'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected POST'))

    def test_rejects_preflight_with_reported_writes(self):
        result = {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT',
                  'authenticated_owner_verified': True, 'database_writes': 1,
                  'visible_tracking_records': 0}
        with patch('phase3_tracking_write_adapter.preflight', return_value=result):
            with self.assertRaisesRegex(ValueError, 'evidence'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected POST'))

    def test_empty_batch_never_uses_network(self):
        data = sample()
        data['proposed_inserts'] = []
        data['proposal_sha256'] = hashlib.sha256(_canonical([]).encode()).hexdigest()
        with patch('phase3_tracking_write_adapter.preflight') as check:
            result = apply_plan(data, OWNER, '', '', '', '', enabled=True)
            self.assertEqual(result['database_writes'], 0)
            check.assert_not_called()

    def test_rejects_preflight_without_verified_evidence(self):
        with patch('phase3_tracking_write_adapter.preflight', return_value={'authenticated_owner_verified': True}):
            with self.assertRaisesRegex(ValueError, 'evidence'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected POST'))

    def test_rejects_preflight_with_reported_writes(self):
        result = {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT',
                  'authenticated_owner_verified': True, 'database_writes': 1,
                  'visible_tracking_records': 0}
        with patch('phase3_tracking_write_adapter.preflight', return_value=result):
            with self.assertRaisesRegex(ValueError, 'evidence'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected POST'))

    def test_empty_batch_never_uses_network(self):
        data = sample()
        data['proposed_inserts'] = []
        data['proposal_sha256'] = hashlib.sha256(_canonical([]).encode()).hexdigest()
        with patch('phase3_tracking_write_adapter.preflight') as check:
            result = apply_plan(data, OWNER, '', '', '', '', enabled=True)
            self.assertEqual(result['database_writes'], 0)
            check.assert_not_called()

    def test_enabled_requires_preflight_before_post(self):
        with patch('phase3_tracking_write_adapter.preflight', side_effect=ValueError('bad identity')):
            with self.assertRaisesRegex(ValueError, 'bad identity'):
                apply_plan(sample(), OWNER, '', '', '', '', enabled=True,
                           opener=lambda *args, **kwargs: self.fail('unexpected write'))

class TestPartialBatchFailures(unittest.TestCase):
    def test_second_insert_failure_reports_confirmed_and_uncertain(self):
        data = sample()
        second = {'user_id': OWNER, 'tracking_id': 'b' * 64,
                  'payload': {'provenance_status': 'VERIFIED_PREGAME', 'grade': 'MISS'}}
        data['proposed_inserts'].append(second)
        data['proposal_sha256'] = hashlib.sha256(_canonical(data['proposed_inserts']).encode()).hexdigest()
        evidence = {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT',
                    'authenticated_owner_verified': True, 'database_writes': 0,
                    'visible_tracking_records': 0}
        class Response:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *args): return False
        calls = []
        def fake_open(request, timeout=15):
            calls.append(request)
            if len(calls) == 2:
                raise TimeoutError('unknown commit state')
            return Response()
        with patch('phase3_tracking_write_adapter.preflight', return_value=evidence):
            with self.assertRaises(PartialTrackingWriteError) as caught:
                apply_plan(data, OWNER, 'https://luxezjthznupdghmexyh.supabase.co',
                           'key', 'token', 'dlindeman333/NFL_Parlays_Test',
                           enabled=True, opener=fake_open)
        self.assertEqual(caught.exception.confirmed_ids, ('a' * 64,))
        self.assertEqual(caught.exception.attempted_id, 'b' * 64)
        self.assertEqual(len(calls), 2)

    def test_first_insert_failure_does_not_claim_zero_writes(self):
        evidence = {'mode': 'TEST_AUTHENTICATED_READ_ONLY_PREFLIGHT',
                    'authenticated_owner_verified': True, 'database_writes': 0,
                    'visible_tracking_records': 0}
        with patch('phase3_tracking_write_adapter.preflight', return_value=evidence):
            with self.assertRaises(PartialTrackingWriteError) as caught:
                apply_plan(sample(), OWNER, 'https://luxezjthznupdghmexyh.supabase.co',
                           'key', 'token', 'dlindeman333/NFL_Parlays_Test',
                           enabled=True, opener=lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(caught.exception.confirmed_ids, ())
        self.assertEqual(caught.exception.attempted_id, 'a' * 64)

if __name__ == '__main__':
    unittest.main()
