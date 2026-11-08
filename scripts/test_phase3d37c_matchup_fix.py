import unittest
from datetime import datetime,timezone
from phase3d37c_crosswalk import assess,canonical_team,build_crosswalk
NOW=datetime(2026,11,8,12,tzinfo=timezone.utc)
EXP='2026-11-08T03:58:36Z'
MATCH=[{'player_id':'123','status':'matched','team_id':'1','opponent_team_id':'2','game_id':'game','kickoff_at':'2026-11-15T21:00Z'}]
ABBR={'1':'LAR','2':'ARI'}
CROSS={'00-0000001':'123'}
def row(**kwargs):
 r={'season':'2026','week':'5','player_id':'00-0000001','name':'Example','team':'LA','next_opponent':'WAS','games_played_to_date':'5','game_status':'completed','pass_yards_last3_avg':'200','pass_yards_season_avg':'210'}
 r.update(kwargs);return r
class Tests(unittest.TestCase):
 def test_aliases(self):
  self.assertEqual(canonical_team('la'),'LAR');self.assertEqual(canonical_team('OAK'),'LV')
 def test_historical_opponent_does_not_block(self):
  result=assess([row()],CROSS,MATCH,ABBR,2026,10,EXP,NOW)
  self.assertEqual(result['matched_projection_players'],1)
  self.assertEqual(result['sample_projections'][0]['opponent'],'ARI')
 def test_latest_completed_week_dedup(self):
  result=assess([row(week='4'),row(week='7',pass_yards_last3_avg='250')],CROSS,MATCH,ABBR,2026,10,EXP,NOW)
  self.assertEqual(result['matched_projection_players'],1)
  self.assertEqual(result['sample_projections'][0]['projections'][0]['projection'],234.0)
 def test_team_mismatch_still_rejected(self):
  result=assess([row(team='SEA')],CROSS,MATCH,ABBR,2026,10,EXP,NOW)
  self.assertEqual(result['stage_counts']['team_mismatch'],1)
 def test_source_week_must_be_prior(self):
  result=assess([row(week='10')],CROSS,MATCH,ABBR,2026,10,EXP,NOW)
  self.assertEqual(result['stage_counts']['source_week_not_prior'],1)
 def test_export_after_kickoff_rejected(self):
  result=assess([row()],CROSS,MATCH,ABBR,2026,10,'2026-11-16T00:00:00Z',NOW)
  self.assertEqual(result['stage_counts']['export_not_point_in_time'],1)
 def test_future_rows_rejected(self):
  result=assess([row(is_future='true')],CROSS,MATCH,ABBR,2026,10,EXP,NOW)
  self.assertEqual(result['stage_counts']['future_row'],1)
 def test_ambiguous_crosswalk_rejected(self):
  result,_=build_crosswalk([{'gsis_id':'00-0000001','espn_id':'123'},{'gsis_id':'00-0000001','espn_id':'456'}])
  self.assertEqual(result,{})
if __name__=='__main__':unittest.main()
