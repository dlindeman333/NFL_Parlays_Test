import unittest
from datetime import datetime,timezone,timedelta
from phase3d37f_pregame import current_week,freshness,prepare

NOW=datetime(2026,11,8,12,tzinfo=timezone.utc)
class Tests(unittest.TestCase):
 def test_current_week(self):
  self.assertEqual(current_week({'season':{'year':2026,'type':2},'week':{'number':10}}),(2026,10))
 def test_reject_preseason(self):
  with self.assertRaises(ValueError):current_week({'season':{'year':2026,'type':1},'week':{'number':10}})
 def test_stale(self):
  self.assertEqual(freshness((NOW-timedelta(hours=13)).isoformat(),NOW,12),'stale_stats_export')
 def test_fresh(self):
  self.assertIsNone(freshness((NOW-timedelta(hours=1)).isoformat(),NOW,12))
 def test_future(self):
  self.assertEqual(freshness((NOW+timedelta(hours=1)).isoformat(),NOW,12),'export_timestamp_in_future')
 def test_no_write_even_when_fresh(self):
  r=prepare({'status':'ok','season':2026,'week':10,'recomputed_player_count':1,'sample_previews':[]},{'generated_at':NOW.isoformat(),'csv_text':'abc'},NOW,12)
  self.assertEqual(r['database_writes'],0)
  self.assertFalse(r['point_in_time_verified'])
  self.assertEqual(r['readiness'],'BLOCKED_FOR_AUTOMATED_SNAPSHOTS')
 def test_missing_players(self):
  r=prepare({'status':'ok','recomputed_player_count':0},{'generated_at':NOW.isoformat(),'csv_text':'abc'},NOW,12)
  self.assertIn('no_recomputed_players',r['blocking_reasons'])
if __name__=='__main__':unittest.main()
