import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from phase3d37c_join_fix import norm_id,assess
from datetime import datetime,timezone,timedelta

class Tests(unittest.TestCase):
 def test_normalization(self):
  self.assertEqual(norm_id('12345.0'),'12345')
  self.assertEqual(norm_id(' 12345 '),'12345')
 def test_staged_missing_id(self):
  row={'season':'2026','week':'9','player_id':'123','name':'Test Player','team':'BUF','next_opponent':'MIA','games_played_to_date':'4','game_status':'final','pass_yards_last3_avg':'200','pass_yards_season_avg':'190'}
  r=assess([row],[],{},2026,10,'2026-11-08T00:00:00Z',datetime(2026,11,8,tzinfo=timezone.utc))
  self.assertEqual(r['stage_counts']['id_absent_from_roster'],1)
 def test_valid_match(self):
  now=datetime(2026,11,8,tzinfo=timezone.utc)
  row={'season':'2026','week':'9','player_id':'123','name':'Test Player','team':'BUF','next_opponent':'MIA','games_played_to_date':'4','game_status':'final','pass_yards_last3_avg':'200','pass_yards_season_avg':'190'}
  m={'player_id':'123','status':'matched','team_id':'2','opponent_team_id':'15','kickoff_at':(now+timedelta(days=2)).isoformat(),'game_id':'100'}
  r=assess([row],[m],{'2':'BUF','15':'MIA'},2026,10,'2026-11-07T00:00:00Z',now)
  self.assertEqual(r['matched_projection_players'],1)
 def test_team_mismatch(self):
  now=datetime(2026,11,8,tzinfo=timezone.utc)
  row={'season':'2026','week':'9','player_id':'123','name':'Test Player','team':'ARI','next_opponent':'MIA','games_played_to_date':'4','game_status':'final','pass_yards_last3_avg':'200','pass_yards_season_avg':'190'}
  m={'player_id':'123','status':'matched','team_id':'2','opponent_team_id':'15','kickoff_at':(now+timedelta(days=2)).isoformat(),'game_id':'100'}
  r=assess([row],[m],{'2':'BUF','15':'MIA'},2026,10,'2026-11-07T00:00:00Z',now)
  self.assertEqual(r['stage_counts']['team_mismatch'],1)
if __name__=='__main__':unittest.main()
