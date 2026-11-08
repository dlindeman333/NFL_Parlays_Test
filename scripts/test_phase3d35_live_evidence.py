import unittest
from phase3d35_live_evidence import validate_url,summarize_injuries,summarize_schedule,supabase_count
class Tests(unittest.TestCase):
 def test_url(self):
  self.assertEqual(validate_url('https://example.supabase.co/'),'https://example.supabase.co')
  with self.assertRaises(ValueError):validate_url('http://example.supabase.co')
 def test_injury_structure(self):
  self.assertEqual(summarize_injuries({'injuries':[{},{}]})['team_groups'],2)
  self.assertFalse(summarize_injuries({})['player_status_verified'])
 def test_scoreboard(self):
  self.assertEqual(summarize_schedule({'events':[{'id':'1','date':'2026-11-08T12:00Z'},{}]})['events_with_id_and_kickoff'],1)
 def test_table_allowlist(self):
  with self.assertRaises(ValueError):supabase_count('https://example.supabase.co','x','nfl_parlay_sync')
if __name__=='__main__':unittest.main()
