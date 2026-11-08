import unittest
from datetime import datetime,timezone,timedelta
from phase3d37c_crosswalk import build_crosswalk,assess
class CrosswalkTests(unittest.TestCase):
 def test_crosswalk(self):
  m,meta=build_crosswalk([{'gsis_id':'00-0023459','espn_id':'12345'}]);self.assertEqual(m['00-0023459'],'12345')
 def test_ambiguous_mapping_rejected(self):
  m,_=build_crosswalk([{'gsis_id':'00-0023459','espn_id':'12345'},{'gsis_id':'00-0023459','espn_id':'99999'}]);self.assertEqual(m,{})
 def test_reverse_ambiguity_rejected(self):
  m,_=build_crosswalk([{'gsis_id':'00-0023459','espn_id':'12345'},{'gsis_id':'00-0023460','espn_id':'12345'}]);self.assertEqual(m,{})
 def test_empty(self):self.assertEqual(build_crosswalk([])[0],{})
 def test_no_write_and_missing_crosswalk(self):
  row={'season':'2026','week':'3','player_id':'00-0023459','name':'Sample','team':'PIT','next_opponent':'CIN','games_played_to_date':'3','game_status':'COMPLETED','pass_yards_last3_avg':'200','pass_yards_season_avg':'210'}
  r=assess([row],{},[],{},2026,10,'2026-11-08T00:00:00Z',datetime(2026,11,8,tzinfo=timezone.utc))
  self.assertEqual(r['stage_counts']['gsis_not_in_crosswalk'],1);self.assertEqual(r['matched_projection_players'],0)
if __name__=='__main__':unittest.main()
