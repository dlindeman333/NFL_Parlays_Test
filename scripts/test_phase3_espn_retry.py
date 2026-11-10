import io,json,unittest
from unittest.mock import patch
from urllib.error import HTTPError,URLError
from phase3d37b_roster_match import fetch

class Response:
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,*args): return b'{"athletes": []}'

class Tests(unittest.TestCase):
    @patch('phase3d37b_roster_match.time.sleep')
    @patch('phase3d37b_roster_match.urlopen')
    def test_transient_404_recovers(self,open_url,sleep):
        open_url.side_effect=[HTTPError('https://example.test',404,'Not found',{},None),Response()]
        self.assertEqual(fetch('https://example.test',delay=0),{'athletes':[]})
        self.assertEqual(open_url.call_count,2)
    @patch('phase3d37b_roster_match.time.sleep')
    @patch('phase3d37b_roster_match.urlopen')
    def test_persistent_404_fails_closed(self,open_url,sleep):
        open_url.side_effect=HTTPError('https://example.test',404,'Not found',{},None)
        with self.assertRaisesRegex(RuntimeError,'HTTP 404'):fetch('https://example.test',delay=0)
        self.assertEqual(open_url.call_count,3)
    @patch('phase3d37b_roster_match.time.sleep')
    @patch('phase3d37b_roster_match.urlopen')
    def test_non_retryable_403(self,open_url,sleep):
        open_url.side_effect=HTTPError('https://example.test',403,'Forbidden',{},None)
        with self.assertRaisesRegex(RuntimeError,'HTTP 403'):fetch('https://example.test',delay=0)
        self.assertEqual(open_url.call_count,1)
    @patch('phase3d37b_roster_match.time.sleep')
    @patch('phase3d37b_roster_match.urlopen')
    def test_temporary_network_error_recovers(self,open_url,sleep):
        open_url.side_effect=[URLError('temporary'),Response()]
        self.assertEqual(fetch('https://example.test',delay=0),{'athletes':[]})

if __name__=='__main__':unittest.main()
