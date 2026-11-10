import datetime as dt
import unittest
from phase3_forecast_snapshot import create_forecast_artifact
from phase3_model_forecast_grading import grade_forecast_artifact
from test_phase3_forecast_snapshot import MANIFEST, CANDIDATE, RAW, NOW

class ForecastGradingTests(unittest.TestCase):
    def setUp(self):
        self.artifact = create_forecast_artifact(MANIFEST, [CANDIDATE], RAW, NOW)
        self.after = dt.datetime(2026, 11, 13, tzinfo=dt.timezone.utc)
        self.obs = {'logical_key': CANDIDATE['logical_key'], 'game_id': '123', 'espn_id': '456',
                    'metric': 'pass_yards', 'status': 'final', 'actual': 240,
                    'final_verified_at_utc': '2026-11-13T00:00:00Z'}
    def test_verified_final_grades_error_not_betting_hit(self):
        r = grade_forecast_artifact(self.artifact, [self.obs], self.after)['payload']
        self.assertEqual(r['counts']['graded'], 1)
        self.assertEqual(r['grades'][0]['absolute_error'], 19.5)
        self.assertEqual(r['sportsbook_hits'], 0)
        self.assertEqual(r['database_writes'], 0)
    def test_missing_final_is_pending(self):
        self.assertEqual(grade_forecast_artifact(self.artifact, [], self.after)['payload']['counts']['pending_final'], 1)
    def test_unverified_final_is_not_graded(self):
        self.assertEqual(grade_forecast_artifact(self.artifact, [{**self.obs, 'status': 'in_progress'}], self.after)['payload']['counts']['invalid_observation'], 1)
    def test_wrong_player_is_not_graded(self):
        self.assertEqual(grade_forecast_artifact(self.artifact, [{**self.obs, 'espn_id': '999'}], self.after)['payload']['counts']['invalid_observation'], 1)
    def test_duplicate_observation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate_or_missing_observation_identity'):
            grade_forecast_artifact(self.artifact, [self.obs, self.obs], self.after)
    def test_tampered_forecast_rejected(self):
        self.artifact['payload']['forecasts'][0]['baseline'] = 100
        with self.assertRaisesRegex(ValueError, 'forecast_artifact_integrity_failure'):
            grade_forecast_artifact(self.artifact, [self.obs], self.after)
    def test_capture_after_kickoff_rejected(self):
        self.artifact['payload']['captured_at_utc'] = '2026-11-14T00:00:00Z'
        from phase3_forecast_snapshot import canonical
        import hashlib
        self.artifact['payload_sha256'] = hashlib.sha256(canonical(self.artifact['payload'])).hexdigest()
        with self.assertRaisesRegex(ValueError, 'forecast_not_captured_pregame'):
            grade_forecast_artifact(self.artifact, [self.obs], dt.datetime(2026,11,15,tzinfo=dt.timezone.utc))

if __name__ == '__main__': unittest.main()
