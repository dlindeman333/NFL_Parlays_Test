import unittest
from datetime import datetime,timezone
from phase3d37d_readiness import valid_weekly_row,recompute,choose_columns,audit
UTC=timezone.utc
class Tests(unittest.TestCase):
 def test_future_week(self):
  self.assertEqual(valid_weekly_row({'season':'2026','week':'10','game_status':'final','game_date':'2026-11-01T12:00:00Z'},2026,10,datetime(2026,11,15,tzinfo=UTC)),'not_prior_week')
 def test_missing_date(self):
  self.assertEqual(valid_weekly_row({'season':'2026','week':'9','game_status':'final'},2026,10,datetime(2026,11,15,tzinfo=UTC)),'missing_game_date')
 def test_recompute(self):
  rows=[{'pass_yards':str(x)} for x in (100,200,300)]
  self.assertEqual(recompute(rows,{'pass_yards':'pass_yards'})['pass_yards']['baseline'],200)
 def test_missing_raw_column(self):
  self.assertIsNone(choose_columns({'pass_yards_last3_avg'})['pass_yards'])
 def test_duplicate_week_block(self):
  base={'player_id':'00-0000001','season':'2026','week':'1','team':'BUF','game_status':'final','game_date':'2026-09-01T00:00:00Z','pass_yards':'100'}
  match={'player_id':'123','status':'matched','team_id':'2','opponent_team_id':'3','game_id':'42','kickoff_at':'2026-11-15T20:00:00Z'}
  r=audit([base,dict(base)],'2026-11-08T00:00:00Z',2026,10,datetime(2026,11,8,tzinfo=UTC),{'00-0000001':'123'},[match],{'2':'BUF','3':'NYJ'})
  self.assertEqual(r['status_counts']['duplicate_week_conflict_players'],1)
  self.assertEqual(r['recomputed_player_count'],0)
 def test_export_after_kickoff(self):
  row={'player_id':'00-0000001','season':'2026','week':'1','team':'BUF','game_status':'final','game_date':'2026-09-01T00:00:00Z','pass_yards':'100'}
  match={'player_id':'123','status':'matched','team_id':'2','opponent_team_id':'3','game_id':'42','kickoff_at':'2026-11-15T20:00:00Z'}
  r=audit([row],'2026-11-16T00:00:00Z',2026,10,datetime(2026,11,16,tzinfo=UTC),{'00-0000001':'123'},[match],{'2':'BUF','3':'NYJ'})
  self.assertEqual(r['recomputed_player_count'],0)
if __name__=='__main__':unittest.main()
