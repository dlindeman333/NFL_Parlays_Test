import unittest,hashlib
from nfl_grade_contract import pick_key,validate_row
from nfl_grade_writer import prepare_rows,write_once
from nfl_package11_grade_plan import canonical_pick

class ContractTests(unittest.TestCase):
 def test_deterministic(self):
  self.assertEqual(pick_key({'side':'over','line':50},0),pick_key({'line':50,'side':'over'},0))
 def test_distinct_index(self):
  self.assertNotEqual(pick_key({'side':'over'},0),pick_key({'side':'over'},1))
 def test_invalid_index(self):
  with self.assertRaises(ValueError):pick_key({},-1)
 def test_invalid_outcome(self):
  with self.assertRaises(ValueError):validate_row(dict(season=2026,week=9,game_id='123',pick_key=pick_key({},0),outcome='win'))
 def test_prepared(self):
  p={'market':'ml','side':'away'}; snap=dict(season=2026,week=9,game_id='123',picks=[p]); cand=dict(season=2026,week=9,game_id='123',pick_index=0,pick_sha256=hashlib.sha256(canonical_pick(p).encode()).hexdigest(),grade='HIT',evidence={})
  result=prepare_rows({'candidates':[cand]},[snap]);self.assertEqual(result['staged_count'],1);self.assertEqual(result['writes'],0)
 def test_changed_pick_blocks(self):
  p={'market':'ml','side':'away'};snap=dict(season=2026,week=9,game_id='123',picks=[p]);cand=dict(season=2026,week=9,game_id='123',pick_index=0,pick_sha256='0'*64,grade='HIT',evidence={})
  with self.assertRaises(ValueError):prepare_rows({'candidates':[cand]},[snap])
 def test_writes_disabled(self):
  with self.assertRaises(PermissionError):write_once([],approval=True,backup_restore_verified=True)
if __name__=='__main__':unittest.main()
