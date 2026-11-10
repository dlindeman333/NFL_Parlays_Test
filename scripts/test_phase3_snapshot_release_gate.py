import datetime as dt
import unittest
from phase3_snapshot_release_gate import audit
NOW=dt.datetime(2026,11,9,16,tzinfo=dt.timezone.utc)
SHA='a'*64
M={'mode':'READ_ONLY_FULL_POPULATION_PREVIEW','source_acquired_at_utc':'2026-11-09T15:00:00Z','source_generated_at':'2026-11-09T14:00:00Z','source_sha256':SHA,'candidate_metrics':1,'source_freshness_blocker':None}
C={'logical_key':'2026/10/g/p/pass_yards','kickoff_at':'2026-11-10T18:00:00Z','source_sha256':SHA}
class GateTests(unittest.TestCase):
 def test_valid_preview_still_blocked(self):
  r=audit(M,[C],NOW);self.assertEqual(r['readiness'],'BLOCKED');self.assertEqual(r['cloud_writes'],0);self.assertIn('upstream_row_publication_times_unverified',r['blocking_reasons'])
 def test_past_kickoff(self):self.assertIn('kickoff_not_safely_ahead',audit(M,[dict(C,kickoff_at='2026-11-09T15:00:00Z')],NOW)['blocking_reasons'])
 def test_duplicate(self):self.assertIn('invalid_or_duplicate_candidate_key',audit(dict(M,candidate_metrics=2),[C,C],NOW)['blocking_reasons'])
 def test_wrong_source(self):self.assertIn('candidate_source_mismatch',audit(M,[dict(C,source_sha256='b'*64)],NOW)['blocking_reasons'])
 def test_bad_source_time(self):self.assertIn('unverified_source_timing',audit(dict(M,source_generated_at='2026-11-09T15:30:00Z'),[C],NOW)['blocking_reasons'])
 def test_missing_candidates(self):self.assertIn('no_candidates',audit(dict(M,candidate_metrics=0),[],NOW)['blocking_reasons'])
if __name__=='__main__':unittest.main()
