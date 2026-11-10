import unittest
from nfl_readonly_grader import grade_pick,audit
class GradingTests(unittest.TestCase):
    def setUp(self):
        self.p={'market':'player','stat':'rec_yards','side':'o','line':49.5,'player_name':'Sample Player','team':'BUF'}
        self.r=[{'season':'2026','week':'9','game_id':'123','name':'Sample Player','team':'BUF','game_status':'COMPLETED','rec_yards':'67','rush_tds':'0','rec_tds':'1','pass_tds':'0'}]
    def test_hit(self): self.assertEqual(grade_pick(self.p,self.r)['status'],'HIT')
    def test_miss(self): self.assertEqual(grade_pick({**self.p,'side':'u'},self.r)['status'],'MISS')
    def test_push(self): self.assertEqual(grade_pick({**self.p,'line':67},self.r)['status'],'PUSH')
    def test_missing_line(self): self.assertEqual(grade_pick({**self.p,'line':None},self.r)['status'],'UNAVAILABLE')
    def test_future_not_graded(self): self.assertEqual(grade_pick(self.p,[{**self.r[0],'game_status':'FUTURE'}])['status'],'UNAVAILABLE')
    def test_ambiguous_not_graded(self): self.assertEqual(grade_pick(self.p,self.r*2)['status'],'UNAVAILABLE')
    def test_unsupported_market(self): self.assertEqual(grade_pick({**self.p,'market':'ml'},self.r)['status'],'UNAVAILABLE')
    def test_td(self): self.assertEqual(grade_pick({**self.p,'stat':'touchdowns','line':0.5},self.r)['status'],'HIT')
    def test_invalid_td(self): self.assertEqual(grade_pick({**self.p,'stat':'touchdowns','line':1.5},self.r)['status'],'UNAVAILABLE')
    def test_cross_game_player_stats_blocked(self):
        result=audit([{'season':2026,'week':9,'game_id':'other-game','picks':[self.p]}],self.r)
        self.assertEqual(result['summary']['UNAVAILABLE'],1)
    def test_missing_game_id_on_stats_blocked(self):
        stats=[{k:v for k,v in self.r[0].items() if k!='game_id'}]
        result=audit([{'season':2026,'week':9,'game_id':'123','picks':[self.p]}],stats)
        self.assertEqual(result['summary']['UNAVAILABLE'],1)
    def test_audit(self):
        report=audit([{'season':2026,'week':9,'game_id':'123','picks':[self.p]}],self.r)
        self.assertEqual(report['summary']['HIT'],1);self.assertEqual(report['database_writes'],0)
if __name__=='__main__': unittest.main()
