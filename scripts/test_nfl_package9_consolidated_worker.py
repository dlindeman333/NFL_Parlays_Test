import os,sys,unittest
sys.path.insert(0,os.path.dirname(__file__))
from nfl_package9_consolidated_worker import build_report,contract_audit
class Tests(unittest.TestCase):
 def test_touchdown_contract_stays_blocked(self):
  snaps=[{'game_id':'1','picks':[{'market':'player','stat':'touchdowns','side':'o'}]}]
  report={'results':[{'game_id':'1','pick_index':0,'status':'UNAVAILABLE'}]}
  self.assertEqual(contract_audit(snaps,report)['unverified_contracts']['touchdown_market_semantics_unverified'],1)
 def test_only_provisional_grade_candidates(self):
  report={'results':[{'game_id':'1','pick_index':0,'status':'HIT','actual':3},{'game_id':'1','pick_index':1,'status':'UNAVAILABLE'}]}
  self.assertEqual(contract_audit([],report)['provisional_candidate_count'],1)
 def test_no_writes(self):
  r=build_report([],{},summary_fetch=lambda _: {})
  self.assertEqual(r['database_writes'],0)
  self.assertFalse(r['write_enabled'])
 def test_unsupported_market_flag(self):
  a=contract_audit([{'game_id':'x','picks':[{'market':'weird'}]}],{'results':[]})
  self.assertEqual(a['unverified_contracts']['unknown_market'],1)
if __name__=='__main__':unittest.main()
