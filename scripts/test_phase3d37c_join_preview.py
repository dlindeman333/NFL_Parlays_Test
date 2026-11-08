import unittest
from datetime import datetime,timezone
from phase3d37c_join_preview import join

class JoinTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,8,8,tzinfo=timezone.utc)
        self.matches=[{'player_id':'123','status':'matched','team_id':'1','opponent_team_id':'2','game_id':'g1','kickoff_at':'2026-11-15T18:00:00Z'}]
        self.abbr={'1':'BUF','2':'MIA'}
        self.row={'season':'2026','week':'9','player_id':'123','name':'Test Player','team':'BUF','next_opponent':'MIA','games_played_to_date':'5','game_status':'final','pass_yards_last3_avg':'200','pass_yards_season_avg':'180'}
    def execute(self,row=None,export='2026-11-08T01:00:00Z'):
        return join([row or self.row],self.matches,self.abbr,2026,10,export,self.now)
    def test_valid_join(self):
        c,e=self.execute();self.assertEqual(len(c),1);self.assertEqual(c[0]['projections'][0]['projection'],192)
    def test_team_mismatch(self):
        r={**self.row,'team':'ARI'};c,e=self.execute(r);self.assertEqual(len(c),0);self.assertEqual(e['team_mismatch'],1)
    def test_opponent_mismatch(self):
        r={**self.row,'next_opponent':'NYJ'};c,e=self.execute(r);self.assertEqual(e['opponent_mismatch'],1)
    def test_future_export(self):
        c,e=self.execute(export='2026-11-16T01:00:00Z');self.assertEqual(e['export_not_point_in_time'],1)
    def test_current_week_row(self):
        c,e=self.execute({**self.row,'week':'10'});self.assertEqual(e['source_week_not_prior'],1)
    def test_unverified_final(self):
        c,e=self.execute({**self.row,'game_status':'unknown'});self.assertEqual(e['unverified_completed_game'],1)
    def test_no_match(self):
        c,e=join([self.row],[],self.abbr,2026,10,'2026-11-08T01:00:00Z',self.now);self.assertEqual(e['unmatched_roster_or_game'],1)
if __name__=='__main__':unittest.main()
