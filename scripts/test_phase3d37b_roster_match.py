import unittest
from datetime import datetime,timezone
from phase3d37b_roster_match import verify, athletes, games
class Tests(unittest.TestCase):
 def test_valid_match(self):
  r=verify({'42':[{'team_id':'1'}]},[{'game_id':'G','team_ids':['1','2'],'kickoff_at':'2099-01-01T00:00:00Z'}],datetime(2026,1,1,tzinfo=timezone.utc));self.assertEqual(r[0]['opponent_team_id'],'2')
 def test_ambiguous(self):
  r=verify({'42':[{'team_id':'1'},{'team_id':'2'}]},[],datetime.now(timezone.utc));self.assertEqual(r[0]['status'],'ambiguous_roster')
 def test_past_game(self):
  r=verify({'42':[{'team_id':'1'}]},[{'game_id':'G','team_ids':['1','2'],'kickoff_at':'2020-01-01T00:00:00Z'}],datetime.now(timezone.utc));self.assertEqual(r[0]['status'],'no_upcoming_game')
 def test_roster_shape(self):self.assertEqual(athletes({'athletes':[{'items':[{'id':'4'}]}]})[0]['id'],'4')
 def test_schedule_shape(self):self.assertEqual(games({'events':[{'id':'G','date':'2099-01-01T00:00:00Z','competitions':[{'competitors':[{'team':{'id':'1'}},{'team':{'id':'2'}}]}]}]})[0]['game_id'],'G')
if __name__=='__main__':unittest.main()
