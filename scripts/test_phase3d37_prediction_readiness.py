import datetime as dt, unittest
from phase3d37_prediction_readiness import choose_rows,parse_time
NOW=dt.datetime(2026,11,8,tzinfo=dt.timezone.utc)
HEADER='season,week,player_id,name,team,next_opponent,games_played_to_date,pass_yards_last3_avg,pass_yards_season_avg,next_game_date,future_team_assignment_provisional\n'
ROW='2026,10,12,Example,BUF,MIA,5,250,200,2026-11-15,false\n'
class TestReadiness(unittest.TestCase):
    def test_reject_naive_time(self): self.assertIsNone(parse_time('2026-11-08T00:00:00'))
    def test_reject_future_export(self): self.assertEqual(choose_rows(HEADER+ROW,NOW,NOW+dt.timedelta(seconds=1))['status'],'blocked_export_timestamp')
    def test_candidate_review_only(self):
        x=choose_rows(HEADER+ROW,NOW,NOW-dt.timedelta(hours=1));self.assertEqual(x['eligible'],1);self.assertFalse(x['snapshot_ready'])
    def test_provisional_assignment_blocked(self):
        x=choose_rows(HEADER+ROW.replace('false','true'),NOW,NOW);self.assertEqual(x['eligible'],0)
    def test_no_future_rows(self):
        x=choose_rows(HEADER.replace('future_team_assignment_provisional','is_future')+ROW.replace('false','true'),NOW,NOW);self.assertEqual(x['eligible'],0)
if __name__=='__main__':unittest.main()
