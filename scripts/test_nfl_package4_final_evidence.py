import unittest
from nfl_package4_final_evidence import normalize_games,evaluate

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.snap=[{'game_id':'123','home_team':'BUF','away_team':'NYJ','picks':[{}]}]
        self.payload={'events':[{'id':'123','status':{'type':{'completed':True,'name':'STATUS_FINAL'}},'competitions':[{'competitors':[{'homeAway':'home','team':{'abbreviation':'BUF'},'score':'21'},{'homeAway':'away','team':{'abbreviation':'NYJ'},'score':'10'}]}]}]}
    def test_final(self):
        r=evaluate(self.snap,normalize_games(self.payload),2026,9)
        self.assertEqual(r['counts'],{'FINAL_SCORE_VERIFIED':1});self.assertEqual(r['database_writes'],0)
    def test_not_final(self):
        self.payload['events'][0]['status']['type']['completed']=False
        self.assertEqual(evaluate(self.snap,normalize_games(self.payload),2026,9)['counts'],{'NOT_FINAL':1})
    def test_mismatch(self):
        self.snap[0]['home_team']='MIA'
        self.assertEqual(evaluate(self.snap,normalize_games(self.payload),2026,9)['counts'],{'TEAM_MISMATCH':1})
    def test_missing(self):
        self.assertEqual(evaluate(self.snap,{},2026,9)['counts'],{'GAME_NOT_FOUND':1})
    def test_no_score(self):
        self.payload['events'][0]['competitions'][0]['competitors'][0]['score']=''
        self.assertEqual(evaluate(self.snap,normalize_games(self.payload),2026,9)['counts'],{'INVALID_FINAL_SCORE':1})
    def test_no_games(self):
        self.assertEqual(normalize_games({}),{})
if __name__=='__main__':unittest.main()
