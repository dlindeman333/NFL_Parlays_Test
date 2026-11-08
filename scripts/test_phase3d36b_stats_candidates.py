import unittest
from phase3d36b_stats_candidates import candidate,preview

BASE={'season':'2026','week':'9','player_id':'123','name':'Example','team':'BUF','next_opponent':'MIA',
      'games_played_to_date':'8','pass_yards_last3_avg':'260','pass_yards_season_avg':'240','game_status':'final'}
class CandidateTests(unittest.TestCase):
 def test_projection(self):
  c,r=candidate(BASE);self.assertIsNone(r);self.assertEqual(c['projections'][0]['projection'],252)
 def test_future_rejected(self):
  self.assertEqual(candidate({**BASE,'is_future':'true'})[1],'future_row')
 def test_missing_data_rejected(self):
  self.assertEqual(candidate({**BASE,'pass_yards_last3_avg':''})[1],'missing_averages')
 def test_insufficient_games(self):
  self.assertEqual(candidate({**BASE,'games_played_to_date':'1'})[1],'insufficient_history')
 def test_latest_week_dedup(self):
  p=preview([BASE,{**BASE,'week':'10','pass_yards_last3_avg':'300'}]);self.assertEqual(p['eligible_unique_players'],1)
  self.assertEqual(p['candidates'][0]['source_week'],'10')
 def test_wrong_season(self):
  self.assertEqual(candidate({**BASE,'season':'2025'})[1],'wrong_season')
if __name__=='__main__':unittest.main()
