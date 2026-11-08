import datetime as dt,unittest
from phase3d37j_storage_dry_run import group_candidates,parse_time
NOW=dt.datetime(2026,11,8,10,tzinfo=dt.timezone.utc)
M={'season':2026,'week':9,'source_sha256':'abc'}
def c(**kw):
 d={'logical_key':'2026/9/123/456/pass_yards','game_id':'123','espn_id':'456','metric':'pass_yards','baseline':200,'kickoff_at':'2026-11-08T18:00Z','source_sha256':'abc'};d.update(kw);return d
class Tests(unittest.TestCase):
 def test_valid(self):
  plans,reasons=group_candidates([c()],M,NOW,set());self.assertEqual(plans[0]['candidate_picks'],1);self.assertEqual(reasons,{})
 def test_existing_skip(self):
  plans,_=group_candidates([c()],M,NOW,{(2026,9,'123')});self.assertEqual(plans[0]['status'],'SKIP_EXISTING')
 def test_kickoff_gate(self):
  plans,reasons=group_candidates([c(kickoff_at='2026-11-08T10:14Z')],M,NOW,set());self.assertEqual(plans,[]);self.assertEqual(reasons['kickoff_gate'],1)
 def test_mismatch_hash(self):self.assertEqual(group_candidates([c(source_sha256='wrong')],M,NOW,set())[1]['source_hash_mismatch'],1)
 def test_duplicate(self):self.assertEqual(group_candidates([c(),c()],M,NOW,set())[1]['duplicate_logical_key'],1)
 def test_identity(self):self.assertEqual(group_candidates([c(logical_key='wrong')],M,NOW,set())[1]['invalid_candidate'],1)
 def test_invalid_time(self):self.assertIsNone(parse_time('not a date'))
 def test_no_writer_methods(self):
  import inspect,phase3d37j_storage_dry_run as mod
  src=inspect.getsource(mod);self.assertNotIn("method='POST'",src);self.assertNotIn("method='PATCH'",src);self.assertNotIn("method='DELETE'",src)
if __name__=='__main__':unittest.main()
