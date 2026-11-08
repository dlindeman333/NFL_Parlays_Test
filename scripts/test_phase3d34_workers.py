import datetime as dt
import unittest
from phase3d34_workers import injury_plan,snapshot_plan,grading_plan
NOW=dt.datetime(2026,11,8,tzinfo=dt.timezone.utc)
class Tests(unittest.TestCase):
 def test_injury_fresh(self):
  r=dict(season=2026,week=10,game_id='g',player_id='p',source='ESPN',designation='Out',source_updated_at='2026-11-07T12:00:00Z')
  self.assertEqual(len(injury_plan([r],[],NOW)['candidate_inserts']),1)
  self.assertEqual(len(injury_plan([r],[r],NOW)['candidate_inserts']),0)
 def test_injury_stale(self):
  r=dict(season=2026,week=10,game_id='g',player_id='p',source='ESPN',designation='Out',source_updated_at='2026-11-01T12:00:00Z')
  self.assertEqual(len(injury_plan([r],[],NOW)['held']),1)
 def test_snapshot_kickoff(self):
  g=dict(season=2026,week=10,game_id='g',kickoff_verified=True,model_output_verified=True,picks=[{'pick_key':'p'}],away_team='BUF',home_team='MIA',model_version='test',kickoff_at='2026-11-09T01:00:00Z')
  self.assertEqual(len(snapshot_plan([g],[],NOW)['eligible_for_future_worker']),1)
  self.assertEqual(len(snapshot_plan([g],[g],NOW)['held']),1)
  g['kickoff_at']='2026-11-07T01:00:00Z'
  self.assertEqual(len(snapshot_plan([g],[],NOW)['held']),1)
 def test_grading(self):
  s=dict(season=2026,week=10,game_id='g',picks=[{'pick_key':'k','stat_mapping_verified':True}])
  f=dict(season=2026,week=10,game_id='g',status='final',stats_verified=True)
  self.assertEqual(len(grading_plan([s],[f],[])['eligible_for_future_grader']),1)
  self.assertEqual(len(grading_plan([s],[],[])['held']),1)
  self.assertEqual(len(grading_plan([s],[f],[dict(season=2026,week=10,game_id='g',pick_key='k')])['held']),1)
if __name__=='__main__': unittest.main()
