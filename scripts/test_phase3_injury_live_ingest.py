import json
import unittest
from datetime import datetime, timezone
from io import BytesIO
from phase3_injury_live_ingest import ingest

URL = 'https://injuries.example.org/export.json'
HOST = 'injuries.example.org'

class Response:
    def __init__(self, raw, url=URL):
        self.raw, self.url = BytesIO(raw), url
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def geturl(self): return self.url
    def read(self, size): return self.raw.read(size)

class IngestTests(unittest.TestCase):
    def test_valid(self):
        data = [{'player_id': 'p1', 'team': 'BUF', 'source': 'source-1',
                 'status': 'QUESTIONABLE', 'observed_at': '2026-11-09T20:00:00+00:00'}]
        result = ingest(URL, HOST, fetch=lambda *a, **k: Response(json.dumps(data).encode()),
                        now=datetime(2026, 11, 9, 21, tzinfo=timezone.utc))
        self.assertEqual(result['validated_records'], 1)
        self.assertFalse(result['injury_sync_complete'])
        self.assertEqual(result['injury_records_written'], 0)
    def test_wrong_host(self):
        with self.assertRaisesRegex(ValueError, 'allowlisted'): ingest(URL, 'other.example.org')
    def test_http(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'): ingest('http://injuries.example.org/', HOST)
    def test_redirect(self):
        with self.assertRaisesRegex(ValueError, 'redirect'):
            ingest(URL, HOST, fetch=lambda *a, **k: Response(b'[]', 'https://other.example.org/'))
    def test_bad_schema(self):
        with self.assertRaisesRegex(ValueError, 'array'):
            ingest(URL, HOST, fetch=lambda *a, **k: Response(b'{}'))
    def test_stale(self):
        data = [{'player_id':'p1','team':'BUF','source':'x','status':'OUT','observed_at':'2026-01-01T00:00:00Z'}]
        with self.assertRaisesRegex(ValueError, 'stale'):
            ingest(URL, HOST, fetch=lambda *a, **k: Response(json.dumps(data).encode()),
                   now=datetime(2026,11,9,tzinfo=timezone.utc))
    def test_large_feed(self):
        with self.assertRaisesRegex(ValueError, 'maximum size'):
            ingest(URL, HOST, fetch=lambda *a, **k: Response(b' ' * 5000001))

if __name__ == '__main__': unittest.main()
