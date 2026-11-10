import datetime as dt
import hashlib
import unittest
from phase3_forecast_snapshot import create_forecast_artifact

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,10,20,0,tzinfo=UTC)
RAW=b'csv example'
SHA=hashlib.sha256(RAW).hexdigest()
MANIFEST={'season':2026,'week':10,'source_sha256':SHA,'source_generated_at':'2026-11-10T19:00:00+00:00','candidate_metrics':1,'source_freshness_blocker':None}
CANDIDATE={'logical_key':'2026/10/123/456/pass_yards','espn_id':'456','game_id':'123','metric':'pass_yards','baseline':220.5,'position':'QB','kickoff_at':'2026-11-12T20:00:00+00:00','source_sha256':SHA,'history_weeks':[8,9]}
class TestForecastArtifact(unittest.TestCase):
    def test_good_forecast_has_no_picks_or_writes(self):
        result=create_forecast_artifact(MANIFEST,[CANDIDATE],RAW,NOW)
        self.assertEqual(result['payload']['forecast_count'],1)
        self.assertEqual(result['payload']['database_writes'],0)
        self.assertEqual(result['payload']['betting_picks_created'],0)
        self.assertEqual(result['payload_sha256'],create_forecast_artifact(MANIFEST,[CANDIDATE],RAW,NOW)['payload_sha256'])
    def test_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):
            create_forecast_artifact(MANIFEST,[CANDIDATE],b'changed',NOW)
    def test_after_kickoff_rejected(self):
        with self.assertRaisesRegex(ValueError,'unsafe_forecast_candidates'):
            create_forecast_artifact(MANIFEST,[CANDIDATE],RAW,dt.datetime(2026,11,13,tzinfo=UTC))
    def test_stale_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'stale_source'):
            create_forecast_artifact({**MANIFEST,'source_freshness_blocker':'stale'},[CANDIDATE],RAW,NOW)
    def test_partial_population_rejected(self):
        with self.assertRaisesRegex(ValueError,'unsafe_forecast_candidates'):
            create_forecast_artifact(MANIFEST,[{**CANDIDATE,'baseline':-1}],RAW,NOW)
    def test_future_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'invalid_source_generated_at'):
            create_forecast_artifact({**MANIFEST,'source_generated_at':'2026-11-15T00:00:00Z'},[CANDIDATE],RAW,NOW)
if __name__=='__main__':unittest.main()
