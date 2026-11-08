import datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from phase3d37l_serializer_dry_run import audit_candidates,inspect_contract_shape
NOW=dt.datetime(2026,11,8,12,tzinfo=dt.timezone.utc)
M={"season":2026,"week":9,"source_sha256":"abc"}
def candidate(**updates):
 c={"logical_key":"2026/9/123/456/pass_yards","game_id":"123","espn_id":"456","metric":"pass_yards","baseline":220.5,"position":"QB","kickoff_at":"2026-11-08T18:00Z","source_sha256":"abc","history_weeks":[1,2,3]};c.update(updates);return c
class Tests(unittest.TestCase):
 def test_valid_baseline_not_betting_pick(self):
  rows,plans,errors=audit_candidates(M,[candidate()],NOW);self.assertEqual(len(rows),1);self.assertEqual(len(plans),1);self.assertNotIn("probability",rows[0]);self.assertEqual(errors,{})
 def test_duplicate(self):
  rows,plans,errors=audit_candidates(M,[candidate(),candidate()],NOW);self.assertEqual(len(rows),1);self.assertEqual(errors["duplicate_identity"],1)
 def test_kickoff(self):
  rows,_,errors=audit_candidates(M,[candidate(kickoff_at="2026-11-08T12:10Z")],NOW);self.assertFalse(rows);self.assertEqual(errors["kickoff_gate"],1)
 def test_source(self):
  _,_,errors=audit_candidates(M,[candidate(source_sha256="wrong")],NOW);self.assertEqual(errors["source_mismatch"],1)
 def test_history(self):
  _,_,errors=audit_candidates(M,[candidate(history_weeks=[9])],NOW);self.assertEqual(errors["invalid_history"],1)
 def test_existing(self):
  _,plans,_=audit_candidates(M,[candidate()],NOW,{(2026,9,"123")});self.assertEqual(plans[0]["status"],"SKIP_EXISTING")
 def test_no_fake_probabilities(self):
  self.assertFalse(inspect_contract_shape([["market","side","probability"]])["serializer_ready"])
 def test_nonfinite(self):
  _,_,errors=audit_candidates(M,[candidate(baseline=float("nan"))],NOW);self.assertEqual(errors["invalid_baseline"],1)
if __name__=="__main__":unittest.main()
