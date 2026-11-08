import unittest
from nfl_package11_grade_plan import build_plan

S={'season':2026,'week':9,'game_id':'g1','picks':[{'market':'ml','side':'a'},{'market':'player','stat':'touchdowns','side':'over'}]}
class TestPlan(unittest.TestCase):
 def test_valid_moneyline(self):
  p=build_plan([S],{'results':[{'game_id':'g1','pick_index':0,'status':'HIT','home_score':10,'away_score':33}]},2026,9)
  self.assertEqual(p['candidate_count'],1);self.assertFalse(p['write_enabled']);self.assertEqual(len(p['candidates'][0]['pick_sha256']),64)
 def test_touchdowns_blocked(self):
  p=build_plan([S],{'results':[{'game_id':'g1','pick_index':1,'status':'HIT'}]},2026,9)
  self.assertEqual(p['candidate_count'],0)
 def test_duplicate_result_rejected(self):
  r={'game_id':'g1','pick_index':0,'status':'HIT'}
  with self.assertRaises(ValueError):build_plan([S],{'results':[r,r]},2026,9)
 def test_unknown_result_rejected(self):
  with self.assertRaises(ValueError):build_plan([S],{'results':[{'game_id':'x','pick_index':0,'status':'HIT'}]},2026,9)
 def test_week_mismatch_rejected(self):
  with self.assertRaises(ValueError):build_plan([S],{'results':[]},2026,10)
 def test_invalid_index_rejected(self):
  with self.assertRaises(ValueError):build_plan([S],{'results':[{'game_id':'g1','pick_index':True,'status':'HIT'}]},2026,9)
 def test_unavailable_not_graded(self):
  p=build_plan([S],{'results':[{'game_id':'g1','pick_index':0,'status':'UNAVAILABLE','reason':'Not final'}]},2026,9)
  self.assertEqual(p['candidate_count'],0)
if __name__=='__main__':unittest.main()
