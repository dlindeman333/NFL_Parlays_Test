import unittest
from nfl_package6_pick_match import grade,evaluate,parse_number
class TestMatch(unittest.TestCase):
 def setUp(self):
  self.pick={'market':'player','stat':'rec_yards','side':'o','line':49.5,'player_name':'A Player','team':'WSH'}
  self.records=[{'player_name':'A Player','player_id':'123','team':'WAS','category':'receiving','stats':{'YDS':'65','REC':'5'}}]
  self.snap={'game_id':'401873037','home_team':'WAS','away_team':'JAX','picks':[self.pick]}
  self.game={'completed':True,'home':{'team':'WSH','score':'24'},'away':{'team':'JAC','score':'21'}}
 def test_hit(self): self.assertEqual(grade(self.pick,self.records)['status'],'HIT')
 def test_miss(self): self.assertEqual(grade({**self.pick,'side':'u'},self.records)['status'],'MISS')
 def test_push(self): self.assertEqual(grade({**self.pick,'line':65},self.records)['status'],'PUSH')
 def test_missing(self): self.assertEqual(grade(self.pick,[])['status'],'UNAVAILABLE')
 def test_duplicate(self): self.assertEqual(grade(self.pick,self.records*2)['status'],'UNAVAILABLE')
 def test_wrong_category(self): self.assertEqual(grade(self.pick,[{**self.records[0],'category':'rushing'}])['status'],'UNAVAILABLE')
 def test_unsupported(self): self.assertEqual(grade({**self.pick,'stat':'touchdowns'},self.records)['status'],'UNAVAILABLE')
 def test_game_market(self): self.assertEqual(grade({**self.pick,'market':'game'},self.records)['status'],'UNAVAILABLE')
 def test_missing_line(self): self.assertEqual(grade({**self.pick,'line':None},self.records)['status'],'UNAVAILABLE')
 def test_nonfinite(self): self.assertIsNone(parse_number('nan'))
 def test_negative(self): self.assertIsNone(parse_number(-1))
 def test_unfinished_no_fetch(self):
  result=evaluate([self.snap],{'401873037':{**self.game,'completed':False}},lambda _:self.fail('should not fetch'))
  self.assertEqual(result['grade_counts']['UNAVAILABLE'],1)
 def test_valid_final(self):
  payload={'boxscore':{'players':[{'team':{'abbreviation':'WSH'},'statistics':[{'name':'receiving','labels':['YDS','REC'],'athletes':[{'athlete':{'id':'123','displayName':'A Player'},'stats':['65','5']}]}]}]}}
  result=evaluate([self.snap],{'401873037':self.game},lambda _:payload)
  self.assertEqual(result['grade_counts']['HIT'],1);self.assertEqual(result['database_writes'],0)
if __name__=='__main__': unittest.main()
