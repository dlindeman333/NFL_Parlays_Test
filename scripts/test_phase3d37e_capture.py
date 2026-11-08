import hashlib, json, os, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from phase3d37e_capture import sha256, classify, build_manifest, capture, verify

CSV='player_id,season,week,team,game_status,game_date,pass_yards\n00-123,2026,1,BUF,final,2026-09-10T20:00:00Z,200\n00-123,2026,11,BUF,scheduled,2026-11-15T20:00:00Z,\n'
NOW=datetime(2026,11,8,12,tzinfo=timezone.utc)
class Tests(unittest.TestCase):
 def test_hash(self):self.assertEqual(sha256(b'abc'),hashlib.sha256(b'abc').hexdigest())
 def test_future_excluded(self):
  a=classify(CSV,2026,10,NOW)
  self.assertEqual(a['counts']['completed_prior_week_rows'],1)
  self.assertEqual(a['counts']['excluded_rows'],1)
 def test_missing_columns(self):self.assertIn('game_date',classify('player_id\na\n',2026,10,NOW)['missing_columns'])
 def test_manifest_blocked(self):
  m=build_manifest({'generated_at':NOW.isoformat()},CSV.encode(),2026,10,NOW,NOW,classify(CSV,2026,10,NOW))
  self.assertFalse(m['historical_point_in_time_verified'])
  self.assertEqual(m['database_writes'],0)
 def test_capture_and_tamper(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'SUPABASE_URL':'https://example.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'fake'}):
   folder=Path(d)
   capture(2026,10,folder,fetch_fn=lambda *_:{'csv_text':CSV,'generated_at':NOW.isoformat(),'record_count':2},clock=lambda:NOW)
   self.assertTrue(verify(folder))
   (folder/'source_stats.csv').write_text('tampered')
   self.assertFalse(verify(folder))
 def test_no_write_http_calls(self):
  import inspect,phase3d37e_capture
  source=inspect.getsource(phase3d37e_capture)
  self.assertNotIn("method='POST'",source)
  self.assertNotIn("method='DELETE'",source)
if __name__=='__main__':unittest.main()
