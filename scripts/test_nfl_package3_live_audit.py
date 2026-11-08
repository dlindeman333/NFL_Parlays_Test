import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from nfl_package3_live_audit import inspect
class AuditTests(unittest.TestCase):
 def test_missing_stat_unavailable(self):
  s=[{'season':2026,'week':9,'game_id':'g','home_team':'BUF','away_team':'NYJ','picks':[{'market':'player','team':'BUF','player_name':'A','stat':'rush_yards','line':50.5,'side':'o'}]}]
  r=inspect(s,[],2026,9);self.assertEqual(r['grade_counts']['UNAVAILABLE'],1);self.assertEqual(r['database_writes'],0)
 def test_wrong_team_rejected(self):
  s=[{'season':2026,'week':9,'game_id':'g','home_team':'BUF','away_team':'NYJ','picks':[{'market':'player','team':'MIA','player_name':'A','stat':'rush_yards','line':50.5,'side':'o'}]}]
  rows=[{'season':'2026','week':'9','name':'A','team':'MIA','game_status':'COMPLETED','rush_yards':'80'}]
  r=inspect(s,rows,2026,9);self.assertEqual(r['grade_counts']['UNAVAILABLE'],1)
 def test_completed_single_row(self):
  s=[{'season':2026,'week':9,'game_id':'g','home_team':'BUF','away_team':'NYJ','picks':[{'market':'player','team':'BUF','player_name':'A','stat':'rush_yards','line':50.5,'side':'o'}]}]
  rows=[{'season':'2026','week':'9','name':'A','team':'BUF','game_status':'COMPLETED','rush_yards':'80'}]
  r=inspect(s,rows,2026,9);self.assertEqual(r['grade_counts']['HIT'],1)
if __name__=='__main__':unittest.main()
