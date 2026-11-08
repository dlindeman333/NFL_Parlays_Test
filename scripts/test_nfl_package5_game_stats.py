import unittest
from nfl_package5_game_stats import team,check_game,extract_player_evidence,build_report,fetch_summary

class TestPackage5(unittest.TestCase):
    def setUp(self):
        self.snap={'game_id':'401873037','home_team':'WAS','away_team':'JAX','picks':[{'market':'player'}]}
        self.game={'completed':True,'home':{'team':'WSH','score':'24'},'away':{'team':'JAC','score':'21'}}
    def test_aliases(self): self.assertEqual(team('WSH'),'WAS');self.assertEqual(team('JAC'),'JAX')
    def test_final_alias(self): self.assertEqual(check_game(self.snap,self.game),'FINAL_VERIFIED')
    def test_home_away(self): self.assertEqual(check_game({**self.snap,'home_team':'JAX'},self.game),'TEAM_MISMATCH')
    def test_not_final(self): self.assertEqual(check_game(self.snap,{**self.game,'completed':False}),'NOT_FINAL')
    def test_no_score(self): self.assertEqual(check_game(self.snap,{**self.game,'home':{'team':'WSH','score':''}}),'INVALID_FINAL_SCORE')
    def test_missing(self): self.assertEqual(check_game(self.snap,None),'GAME_NOT_FOUND')
    def test_boxscore(self):
        payload={'boxscore':{'players':[{'team':{'abbreviation':'WSH'},'statistics':[{'name':'passing','labels':['C/ATT','YDS'],'athletes':[{'athlete':{'id':'12','displayName':'A B'},'stats':['20/30','250']}]}]}]}}
        rows=extract_player_evidence(payload)
        self.assertEqual(rows[0]['stats']['YDS'],'250');self.assertEqual(rows[0]['team'],'WAS')
    def test_invalid_stats_rejected(self):
        p={'boxscore':{'players':[{'statistics':[{'labels':['YDS'],'athletes':[{'athlete':{},'stats':['2','3']}]}]}]}}
        self.assertEqual(extract_player_evidence(p),[])
    def test_report_no_write(self):
        r=build_report([self.snap],{'401873037':self.game},lambda _: {'boxscore':{'players':[]}})
        self.assertEqual(r['counts']['NO_BOX_SCORE_RECORDS'],1);self.assertEqual(r['database_writes'],0)
    def test_unfinished_no_fetch(self):
        r=build_report([self.snap],{'401873037':{**self.game,'completed':False}},lambda _: self.fail('must not fetch'))
        self.assertEqual(r['counts']['NOT_FINAL'],1)
    def test_invalid_id(self):
        with self.assertRaises(ValueError): fetch_summary('http://example.com')
if __name__=='__main__': unittest.main()
