import unittest
from nfl_package7_integrated_preview import grade_compound, evaluate

P = {'market':'player','stat':'pass_completions','side':'o','line':19.5,'player_name':'Jane Doe','team':'BUF'}
R = [{'category':'passing','player_name':'Jane Doe','team':'BUF','player_id':'123','stats':{'C/ATT':'21/30'}}]
class TestContract(unittest.TestCase):
    def test_completions(self): self.assertEqual(grade_compound(P,R)['status'],'HIT')
    def test_attempts(self): self.assertEqual(grade_compound({**P,'stat':'pass_attempts','line':30},R)['status'],'PUSH')
    def test_bad_compound(self): self.assertEqual(grade_compound(P,[{**R[0],'stats':{'C/ATT':'21-30'}}])['status'],'UNAVAILABLE')
    def test_inconsistent(self): self.assertEqual(grade_compound(P,[{**R[0],'stats':{'C/ATT':'31/30'}}])['status'],'UNAVAILABLE')
    def test_ambiguous(self): self.assertEqual(grade_compound(P,R+R)['status'],'UNAVAILABLE')
    def test_missing_line(self): self.assertEqual(grade_compound({**P,'line':None},R)['status'],'UNAVAILABLE')
    def test_unverified_market(self): self.assertEqual(grade_compound({'market':'game','stat':'total','side':'o','line':44.5},R)['status'],'UNAVAILABLE')
    def test_unfinished(self):
        snap={'game_id':'123456789','home_team':'BUF','away_team':'NYJ','picks':[P]}
        out=evaluate([snap],{'123456789':{'completed':False}},lambda _: (_ for _ in ()).throw(Exception('must not call')))
        self.assertEqual(out['grade_counts']['UNAVAILABLE'],1)
        self.assertEqual(out['database_writes'],0)
    def test_final(self):
        snap={'game_id':'123456789','home_team':'BUF','away_team':'NYJ','picks':[P]}
        game={'completed':True,'home':{'team':'BUF','score':'24'},'away':{'team':'NYJ','score':'17'}}
        payload={'boxscore':{'players':[{'team':{'abbreviation':'BUF'},'statistics':[{'name':'passing','labels':['C/ATT'],'athletes':[{'athlete':{'id':'123','displayName':'Jane Doe'},'stats':['21/30']}]}]}]}}
        out=evaluate([snap],{'123456789':game},lambda _:payload)
        self.assertEqual(out['grade_counts']['HIT'],1)
        self.assertEqual(out['official_grades_written'],0)
if __name__=='__main__':unittest.main()
