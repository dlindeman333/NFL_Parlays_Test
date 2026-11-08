import unittest
from datetime import datetime, timedelta, timezone
from phase3d37g_forward_gate import evaluate, metric_allowed, stable_key

NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
GAME = {'game_id':'12345', 'kickoff_at':(NOW+timedelta(hours=3)).isoformat(), 'team_ids':['1','2'], 'status':'STATUS_SCHEDULED'}
ROSTER = {'42':[{'team_id':'1','position':'QB'}]}
SAMPLE = [{'espn_id':'42','game_id':'12345','kickoff_at':GAME['kickoff_at'], 'metrics':{'pass_yards':{'baseline':250}, 'rec_yards':{'baseline':0}, 'rush_yards':{'baseline':0}}}]

class ForwardGateTests(unittest.TestCase):
    def test_position_filter(self):
        self.assertTrue(metric_allowed('QB','pass_yards',200))
        self.assertFalse(metric_allowed('QB','rec_yards',80))
        self.assertFalse(metric_allowed('WR','rec_yards',0))
    def test_stable_key_independent_of_source(self):
        self.assertEqual(stable_key(2026,9,'12345','42','pass_yards'),'2026/9/12345/42/pass_yards')
    def test_accepted_sample(self):
        result=evaluate(SAMPLE,ROSTER,[GAME],NOW,2026,9,NOW.isoformat())
        self.assertEqual(result['sample_metrics_passed'],1)
    def test_reject_late_kickoff(self):
        game=dict(GAME,kickoff_at=(NOW+timedelta(minutes=10)).isoformat())
        sample=[dict(SAMPLE[0],kickoff_at=game['kickoff_at'])]
        self.assertEqual(evaluate(sample,ROSTER,[game],NOW,2026,9,NOW.isoformat())['sample_metrics_passed'],0)
    def test_reject_stale_source(self):
        old=(NOW-timedelta(hours=20)).isoformat()
        self.assertEqual(evaluate(SAMPLE,ROSTER,[GAME],NOW,2026,9,old)['sample_metrics_passed'],0)
    def test_reject_wrong_game(self):
        self.assertEqual(evaluate([dict(SAMPLE[0],game_id='999')],ROSTER,[GAME],NOW,2026,9,NOW.isoformat())['sample_metrics_passed'],0)
    def test_reject_unscheduled_game(self):
        game=dict(GAME,status='STATUS_IN_PROGRESS')
        self.assertEqual(evaluate(SAMPLE,ROSTER,[game],NOW,2026,9,NOW.isoformat())['sample_metrics_passed'],0)
    def test_duplicate_identity(self):
        result=evaluate(SAMPLE+SAMPLE,ROSTER,[GAME],NOW,2026,9,NOW.isoformat())
        self.assertEqual(result['sample_metrics_passed'],1)
        self.assertEqual(result['status_counts']['duplicate_logical_identity'],1)

if __name__=='__main__': unittest.main()
