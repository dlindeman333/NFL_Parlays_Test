import inspect, unittest
from unittest.mock import patch
import phase3d37i_storage_audit as a
class AuditTests(unittest.TestCase):
 def test_table_list(self): self.assertEqual(len(a.TABLES),3)
 def test_no_mutation_http(self): self.assertIn("method='GET'",inspect.getsource(a.get_json))
 def test_no_credentials_in_report(self):
  with patch.object(a,'audit_table',return_value={'table':'example','observed_columns':['id']}):
   result=a.audit('https://example.test','secret')
  self.assertNotIn('secret',str(result));self.assertEqual(result['write_operations'],0)
 def test_failures_sanitized(self):
  with patch.object(a,'audit_table',side_effect=RuntimeError('private secret')):
   result=a.audit('https://example.test','secret')
  self.assertNotIn('private secret',str(result));self.assertEqual(len(result['tables']),3)
 def test_readiness_blocked(self):
  with patch.object(a,'audit_table',return_value={}): self.assertTrue(a.audit('https://x','k')['readiness'].startswith('BLOCKED'))
if __name__=='__main__': unittest.main()
