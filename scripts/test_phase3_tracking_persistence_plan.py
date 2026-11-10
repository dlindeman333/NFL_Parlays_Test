import unittest
from phase3_tracking_persistence_plan import plan

UID = 'test-user'
KEY = 'a' * 64
ROW = {'tracking_id': KEY, 'grade': 'HIT', 'provenance_status': 'VERIFIED_PREGAME'}
EXPORT = {'mode': 'OFFLINE_GRADE_EXPORT', 'ready': True, 'database_writes': 0, 'rows': [ROW]}

class PersistencePlanTests(unittest.TestCase):
    def test_new_row_staged_without_write(self):
        result = plan(EXPORT, [], UID)
        self.assertEqual(result['database_writes'], 0)
        self.assertFalse(result['activation_allowed'])
        self.assertEqual(result['proposed_inserts'][0]['user_id'], UID)
    def test_idempotent_existing_record_preserved(self):
        result = plan(EXPORT, [{'user_id': UID, 'tracking_id': KEY, 'payload': ROW}], UID)
        self.assertEqual(result['existing_preserved'], [KEY])
        self.assertEqual(result['proposed_inserts'], [])
    def test_conflicting_record_not_overwritten(self):
        result = plan(EXPORT, [{'user_id': UID, 'tracking_id': KEY, 'payload': {'grade': 'MISS'}}], UID)
        self.assertEqual(result['conflicts_blocked'], [KEY])
        self.assertEqual(result['proposed_inserts'], [])
    def test_other_users_data_rejected(self):
        with self.assertRaises(ValueError):
            plan(EXPORT, [{'user_id': 'other', 'tracking_id': KEY, 'payload': ROW}], UID)
    def test_unverified_export_rejected(self):
        with self.assertRaises(ValueError):
            plan({**EXPORT, 'rows': [{**ROW, 'provenance_status': 'UNVERIFIED'}]}, [], UID)
    def test_duplicate_tracking_ids_rejected(self):
        with self.assertRaises(ValueError):
            plan({**EXPORT, 'rows': [ROW, ROW]}, [], UID)
    def test_synthetic_security_record_rejected(self):
        for flag in ({'synthetic': True}, {'exclude_from_grading': True},
                     {'exclude_from_accuracy': True}, {'record_type': 'RLS_SECURITY_TEST'}):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'Synthetic'):
                plan({**EXPORT, 'rows': [{**ROW, **flag}]}, [], UID)

    def test_deterministic_plan(self):
        self.assertEqual(plan(EXPORT, [], UID), plan(EXPORT, [], UID))

if __name__ == '__main__':
    unittest.main()
