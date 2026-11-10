import io
import json
import unittest
from urllib.parse import urlsplit
from phase3_tracking_live_preflight import preflight

USER = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
URL = 'https://luxezjthznupdghmexyh.supabase.co'
REPO = 'dlindeman333/NFL_Parlays_Test'


class Response(io.BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *_): self.close()


class PreflightTests(unittest.TestCase):
    def test_owner_read_only(self):
        methods = []
        def opener(req, timeout):
            methods.append(req.get_method())
            payload = {'id': USER} if urlsplit(req.full_url).path == '/auth/v1/user' else [{'user_id': USER, 'tracking_id': 'x', 'payload': {}}]
            return Response(json.dumps(payload).encode())
        result = preflight(URL, 'public', 'token', USER, REPO, opener)
        self.assertEqual(methods, ['GET', 'GET'])
        self.assertEqual(result['visible_tracking_records'], 1)
        self.assertFalse(result['ready_for_write_activation'])

    def test_multiple_pages_are_counted(self):
        from urllib.parse import parse_qs
        offsets = []
        def opener(req, timeout):
            if urlsplit(req.full_url).path == '/auth/v1/user':
                return Response(json.dumps({'id': USER}).encode())
            offset = int(parse_qs(urlsplit(req.full_url).query)['offset'][0])
            offsets.append(offset)
            count = 1000 if offset == 0 else 2
            return Response(json.dumps([{'user_id': USER, 'tracking_id': str(offset + i), 'payload': {}} for i in range(count)]).encode())
        result = preflight(URL, 'public', 'token', USER, REPO, opener)
        self.assertEqual(result['visible_tracking_records'], 1002)
        self.assertEqual(offsets, [0, 1000])

    def test_duplicate_across_pages_rejected(self):
        def opener(req, timeout):
            if urlsplit(req.full_url).path == '/auth/v1/user':
                return Response(json.dumps({'id': USER}).encode())
            from urllib.parse import parse_qs
            offset = int(parse_qs(urlsplit(req.full_url).query)['offset'][0])
            ids = [str(i) for i in range(1000)] if offset == 0 else ['999']
            return Response(json.dumps([{'user_id': USER, 'tracking_id': key} for key in ids]).encode())
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            preflight(URL, 'public', 'token', USER, REPO, opener)

    def test_production_rejected_before_network(self):
        def fail(*args, **kwargs): raise AssertionError('Network must not be accessed')
        for url in ('https://wpvuunwtyxycqfjwuzkn.supabase.co', URL + '.evil.com', URL + ':8443', URL + '/rest/v1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                preflight(url, 'public', 'token', USER, REPO, fail)

    def test_wrong_repository_rejected(self):
        with self.assertRaises(ValueError):
            preflight(URL, 'public', 'token', USER, 'dlindeman333/NFL_Parlays')

    def test_wrong_identity_rejected_without_table_access(self):
        calls = []
        def opener(req, timeout):
            calls.append(req.full_url)
            return Response(json.dumps({'id': 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'}).encode())
        with self.assertRaises(ValueError):
            preflight(URL, 'public', 'token', USER, REPO, opener)
        self.assertEqual(len(calls), 1)

    def test_cross_owner_row_rejected(self):
        def opener(req, timeout):
            payload = {'id': USER} if '/auth/v1/user' in req.full_url else [{'user_id': 'other'}]
            return Response(json.dumps(payload).encode())
        with self.assertRaises(ValueError):
            preflight(URL, 'public', 'token', USER, REPO, opener)


if __name__ == '__main__': unittest.main()
