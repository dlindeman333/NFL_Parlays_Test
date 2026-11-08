import unittest
from nfl_package8_market_grader import grade_moneyline,grade_pick,evaluate
GAME={'completed':True,'home':{'team':'BUF','score':'24'},'away':{'team':'MIA','score':'17'}}
SNAP={'game_id':'401873037','home_team':'BUF','away_team':'MIA','picks':[{'market':'ml','side':'h'},{'market':'ml','side':'a'},{'market':'player','stat':'touchdowns','side':'o','line':0.5}]}
class MarketTests(unittest.TestCase):
 def test_home_win(self):self.assertEqual(grade_moneyline({'market':'ml','side':'h'},GAME)['status'],'HIT')
 def test_away_loss(self):self.assertEqual(grade_moneyline({'market':'ml','side':'a'},GAME)['status'],'MISS')
 def test_tie_unavailable(self):self.assertEqual(grade_moneyline({'market':'ml','side':'h'},{**GAME,'away':{'team':'MIA','score':'24'}})['status'],'UNAVAILABLE')
 def test_invalid_side(self):self.assertEqual(grade_moneyline({'market':'ml','side':'o'},GAME)['status'],'UNAVAILABLE')
 def test_touchdowns_fail_closed(self):self.assertEqual(grade_pick(SNAP['picks'][2],GAME,[])['status'],'UNAVAILABLE')
 def test_final_moneyline_without_boxscore(self):
  r=evaluate([SNAP],{'401873037':GAME},lambda gid: (_ for _ in ()).throw(OSError('unavailable')))
  self.assertEqual(r['grade_counts'],{'HIT':1,'MISS':1,'UNAVAILABLE':1});self.assertEqual(r['database_writes'],0)
 def test_not_final(self):
  r=evaluate([SNAP],{'401873037':{**GAME,'completed':False}})
  self.assertEqual(r['grade_counts'],{'UNAVAILABLE':3})
 def test_wrong_teams(self):
  r=evaluate([SNAP],{'401873037':{**GAME,'home':{'team':'NYJ','score':'24'}}})
  self.assertEqual(r['grade_counts'],{'UNAVAILABLE':3})
 def test_missing_game(self):self.assertEqual(evaluate([SNAP],{})['grade_counts'],{'UNAVAILABLE':3})
if __name__=='__main__':unittest.main()
