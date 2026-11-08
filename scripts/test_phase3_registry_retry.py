import sys,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).parent))
import phase3d37c_crosswalk as c
class RetryTests(unittest.TestCase):
 def test_504_retries_and_recovers(self):
  response=MagicMock();response.__enter__.return_value.read.return_value=b'gsis_id,espn_id\n00-1234567,123\n'
  with patch.object(c,'urlopen',side_effect=[HTTPError(c.REGISTRY_URL,504,'timeout',{},None),response]) as req,patch.object(c.time,'sleep'):
   self.assertEqual(c.download_registry(c.REGISTRY_URL)[0]['espn_id'],'123');self.assertEqual(req.call_count,2)
 def test_404_does_not_retry(self):
  with patch.object(c,'urlopen',side_effect=HTTPError(c.REGISTRY_URL,404,'not found',{},None)) as req:
   with self.assertRaises(HTTPError):c.download_registry(c.REGISTRY_URL)
   self.assertEqual(req.call_count,1)
 def test_unapproved_url_rejected(self):
  with self.assertRaises(ValueError):c.download_registry('https://example.org')
if __name__=='__main__':unittest.main()
