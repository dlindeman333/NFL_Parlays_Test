import unittest
from nfl_package10_scheduled_worker import resolve_week,select_week,run
from unittest.mock import patch

class ScheduleTests(unittest.TestCase):
 def test_manual(self): self.assertEqual(resolve_week({'NFL_SEASON':'2026','NFL_WEEK':'9'}),(2026,9))
 def test_auto(self): self.assertEqual(resolve_week({},lambda:(2026,10)),(2026,10))
 def test_partial_rejected(self):
  with self.assertRaises(ValueError): resolve_week({'NFL_WEEK':'9'})
 def test_out_of_range(self):
  with self.assertRaises(ValueError): resolve_week({'NFL_SEASON':'2026','NFL_WEEK':'99'})
 def test_week_payload(self): self.assertEqual(select_week({'leagues':[{'season':{'year':2026,'type':2}}],'week':{'number':9}}),(2026,9))
 def test_postseason_rejected(self):
  with self.assertRaises(ValueError): select_week({'leagues':[{'season':{'year':2026,'type':3}}],'week':{'number':1}})
 def test_no_data_no_writes(self):
  with patch.dict('os.environ',{'SUPABASE_URL':'https://example.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'dummy'}):
   report=run(2026,9,fetch_rows=lambda *a:[],scoreboard_fetch=lambda *a:{'events':[]})
  self.assertEqual(report['database_writes'],0)
  self.assertFalse(report['grade_write_enabled'])
 def test_truncation(self):
  with patch.dict('os.environ',{'SUPABASE_URL':'https://example.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'dummy'}):
   with self.assertRaises(ValueError):run(2026,9,fetch_rows=lambda *a:[{}]*1000,scoreboard_fetch=lambda *a:{'events':[]})
if __name__=='__main__': unittest.main()
