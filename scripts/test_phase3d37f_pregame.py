import unittest
import hashlib
from unittest.mock import patch
from pathlib import Path
import tempfile
from datetime import datetime,timezone,timedelta
from phase3d37f_pregame import current_week,freshness,prepare,main

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
 def test_changed_csv_with_same_timestamp_blocks_preview(self):
  import sys
  source={'generated_at':NOW.isoformat(),'csv_text':'new contents'}
  stale_hash=hashlib.sha256(b'old contents').hexdigest()
  readiness={'status':'ok','export_generated_at':NOW.isoformat(),'source_csv_sha256':stale_hash}
  with tempfile.TemporaryDirectory() as directory:
   output=Path(directory)/'report.json'
   with patch('phase3d37f_pregame.fetch_latest',return_value=source), patch('phase3d37f_pregame.readiness_run',return_value=readiness), patch.dict('phase3d37f_pregame.os.environ',{'SUPABASE_URL':'https://luxezjthznupdghmexyh.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'test','GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays_Test'}), patch.object(sys,'argv',['prog','--season','2026','--week','10','--output',str(output)]):
    with self.assertRaisesRegex(ValueError,'Source changed'):
     main()
   self.assertFalse(output.exists())
 def test_matching_csv_hash_remains_read_only(self):
  import sys,json
  source={'generated_at':NOW.isoformat(),'csv_text':'same contents'}
  source_hash=hashlib.sha256(source['csv_text'].encode()).hexdigest()
  readiness={'status':'ok','export_generated_at':NOW.isoformat(),'source_csv_sha256':source_hash,'recomputed_player_count':1,'sample_previews':[]}
  with tempfile.TemporaryDirectory() as directory:
   output=Path(directory)/'report.json'
   with patch('phase3d37f_pregame.fetch_latest',return_value=source), patch('phase3d37f_pregame.readiness_run',return_value=readiness), patch.dict('phase3d37f_pregame.os.environ',{'SUPABASE_URL':'https://luxezjthznupdghmexyh.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'test','GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays_Test'}), patch.object(sys,'argv',['prog','--season','2026','--week','10','--output',str(output)]):
    self.assertEqual(main(),0)
   report=json.loads(output.read_text())
   self.assertEqual(report['source_csv_sha256'],source_hash)
   self.assertEqual(report['database_writes'],0)
   self.assertFalse(report['point_in_time_verified'])
 def test_production_project_rejected_before_fetch(self):
  import sys
  with patch('phase3d37f_pregame.fetch_latest') as fetcher, patch.dict('phase3d37f_pregame.os.environ',{'SUPABASE_URL':'https://wpvuunwtyxycqfjwuzkn.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'test','GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays_Test'}), patch.object(sys,'argv',['prog','--season','2026','--week','10']):
   with self.assertRaisesRegex(ValueError,'TEST project'):
    main()
   fetcher.assert_not_called()
 def test_production_repository_rejected_before_fetch(self):
  import sys
  with patch('phase3d37f_pregame.fetch_latest') as fetcher, patch.dict('phase3d37f_pregame.os.environ',{'SUPABASE_URL':'https://luxezjthznupdghmexyh.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'test','GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays'}), patch.object(sys,'argv',['prog','--season','2026','--week','10']):
   with self.assertRaisesRegex(ValueError,'TEST GitHub repository'):
    main()
   fetcher.assert_not_called()
 def test_missing_players(self):
  r=prepare({'status':'ok','recomputed_player_count':0},{'generated_at':NOW.isoformat(),'csv_text':'abc'},NOW,12)
  self.assertIn('no_recomputed_players',r['blocking_reasons'])
if __name__=='__main__':unittest.main()
