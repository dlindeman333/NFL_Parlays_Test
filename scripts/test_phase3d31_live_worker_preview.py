import unittest
from unittest.mock import patch
from scripts.phase3d31_live_worker_preview import endpoint,fetch_count

class FakeResponse:
    headers={'Content-Range':'0-0/27'}
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return b'[{"private":"do-not-log"}]'

class Tests(unittest.TestCase):
    def test_url_restricted(self):
        with self.assertRaises(ValueError):endpoint('http://evil.test','nfl_prediction_grades')
    def test_table_restricted(self):
        with self.assertRaises(ValueError):endpoint('https://example.supabase.co','nfl_parlay_sync')
    @patch('scripts.phase3d31_live_worker_preview.urlopen',return_value=FakeResponse())
    def test_read_only_count(self,mock):
        result=fetch_count('https://example.supabase.co','fake','nfl_prediction_snapshots')
        self.assertEqual(result,{'row_count':27,'reachable':True})
        self.assertEqual(mock.call_args.args[0].get_method(),'GET')

if __name__=='__main__':unittest.main()
