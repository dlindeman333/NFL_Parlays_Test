import unittest
from nfl_readonly_grader import grade_pick, audit

class GameIdentityTests(unittest.TestCase):
    def setUp(self):
        self.pick = {'market':'player','stat':'rec_yards','side':'o','line':49.5,'player_name':'Example Player','team':'BUF'}
        self.row = {'season':'2026','week':'10','name':'Example Player','team':'BUF','game_status':'COMPLETED','rec_yards':'80','game_id':'game-A'}

    def test_matching_game_can_grade(self):
        self.assertEqual(grade_pick(self.pick,[self.row], 'game-A')['status'],'HIT')

    def test_other_game_cannot_grade(self):
        result = grade_pick(self.pick,[self.row], 'game-B')
        self.assertEqual(result['status'],'UNAVAILABLE')

    def test_audit_propagates_game_identity(self):
        snap = {'season':2026,'week':10,'game_id':'game-B','picks':[self.pick]}
        self.assertEqual(audit([snap],[self.row])['summary'],{'UNAVAILABLE':1})

    def test_legacy_stats_without_game_id_unavailable(self):
        row = {k:v for k,v in self.row.items() if k!='game_id'}
        self.assertEqual(grade_pick(self.pick,[row], 'game-A')['status'],'UNAVAILABLE')

if __name__=='__main__': unittest.main()
