import io
import json
import unittest
from phase3_tracking_live_plan import build_live_plan

USER = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
URL = 'https://luxezjthznupdghmexyh.supabase.co'
REPO = 'dlindeman333/NFL_Parlays_Test'
KEY = 'a' * 64

class Response(io.BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

class LivePlanTests(unittest.TestCase):
    def export(self):
        return {'mode': 'OFFLINE_GRADE_EXPORT', 'ready': True, 'database_writes': 0,
                'rows': [{'tracking_id': KEY, 'grade': 'HIT', 'provenance_status': 'VERIFIED_PREGAME'}]}

    def opener(self, existing, methods):
        def open_request(req, timeout):
            methods.append(req.get_method())
            data = {'id': USER} if '/auth/v1/user' in req.full_url else existing
            return Response(json.dumps(data).encode())
        return open_request

    def test_new_record_is_planned_never_written(self):
        methods = []
        result = build_live_plan(self.export(), URL, 'key', 'token', USER, REPO, self.opener([], methods))
        self.assertEqual(methods, ['GET', 'GET'])
        self.assertEqual(len(result['proposed_inserts']), 1)
        self.assertFalse(result['activation_allowed'])
        self.assertEqual(result['database_writes'], 0)

    def test_existing_identical_record_is_preserved(self):
        methods = []
        record = {'user_id': USER, 'tracking_id': KEY, 'payload': self.export()['rows'][0]}
        result = build_live_plan(self.export(), URL, 'key', 'token', USER, REPO, self.opener([record], methods))
        self.assertEqual(result['existing_preserved'], [KEY])
        self.assertFalse(result['proposed_inserts'])

    def test_conflict_is_blocked(self):
        methods = []
        record = {'user_id': USER, 'tracking_id': KEY, 'payload': {'grade': 'MISS'}}
        result = build_live_plan(self.export(), URL, 'key', 'token', USER, REPO, self.opener([record], methods))
        self.assertEqual(result['conflicts_blocked'], [KEY])
        self.assertFalse(result['activation_allowed'])

    def test_cross_owner_is_rejected(self):
        methods = []
        record = {'user_id': 'other', 'tracking_id': KEY, 'payload': {}}
        with self.assertRaises(ValueError):
            build_live_plan(self.export(), URL, 'key', 'token', USER, REPO, self.opener([record], methods))
        self.assertEqual(methods, ['GET', 'GET'])

if __name__ == '__main__': unittest.main()
