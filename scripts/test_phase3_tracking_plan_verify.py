import copy
import unittest
from phase3_tracking_persistence_plan import plan
from phase3_tracking_plan_verify import verify

USER = 'account-A'
KEY = 'a' * 64
ROW = {'tracking_id': KEY, 'grade': 'HIT', 'provenance_status': 'VERIFIED_PREGAME'}
EXPORT = {'mode': 'OFFLINE_GRADE_EXPORT', 'ready': True, 'database_writes': 0, 'rows': [ROW]}

class PlanVerifyTests(unittest.TestCase):
    def setUp(self):
        self.data = plan(EXPORT, [], USER)

    def test_valid_read_only_plan(self):
        self.assertEqual(verify(self.data, USER)['database_writes'], 0)

    def test_wrong_user_rejected(self):
        with self.assertRaises(ValueError): verify(self.data, 'account-B')

    def test_tampered_grade_rejected(self):
        data = copy.deepcopy(self.data)
        data['proposed_inserts'][0]['payload']['grade'] = 'MISS'
        with self.assertRaises(ValueError): verify(data, USER)

    def test_tampered_fingerprint_rejected(self):
        data = copy.deepcopy(self.data)
        data['proposal_sha256'] = '0' * 64
        with self.assertRaises(ValueError): verify(data, USER)

    def test_conflicts_rejected(self):
        data = copy.deepcopy(self.data)
        data['conflicts_blocked'] = [KEY]
        with self.assertRaises(ValueError): verify(data, USER)

    def test_write_unlock_rejected(self):
        data = copy.deepcopy(self.data)
        data['activation_allowed'] = True
        with self.assertRaises(ValueError): verify(data, USER)

if __name__ == '__main__': unittest.main()
