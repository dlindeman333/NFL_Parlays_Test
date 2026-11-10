import unittest
from datetime import datetime,timedelta,timezone
from phase3d37h_full_manifest import build_manifest
UTC=timezone.utc
class FullManifestTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,11,8,12,tzinfo=UTC);self.kick=self.now+timedelta(hours=3)
  self.rows=[dict(player_id='00-0000001',season='2026',week=str(w),team='LAR',game_status='final',game_date=(self.now-timedelta(days=7*(5-w))).isoformat(),pass_yards=str(100+w*10),is_future='false') for w in (1,2,3)]
  self.matches=[dict(player_id='123',status='matched',team_id='1',game_id='999',kickoff_at=self.kick.isoformat())]
  self.schedule=[dict(game_id='999',kickoff_at=self.kick.isoformat(),status='scheduled')]
 def call(self,**kwargs):
  a=dict(rows=self.rows,crosswalk={'00-0000001':'123'},matches=self.matches,abbr={'1':'LA'},positions={'123':'QB'},schedule=self.schedule,season=2026,week=9,now=self.now,export_time=(self.now-timedelta(hours=1)).isoformat(),source_hash='abc')
  a.update(kwargs);return build_manifest(**a)
 def test_full_population_metrics(self):
  entries,counts,_,_=self.call();self.assertEqual(len(entries),1);self.assertEqual(entries[0]['metric'],'pass_yards')
 def test_stable_identity(self):
  a=self.call()[0];b=self.call()[0];self.assertEqual(a[0]['logical_key'],b[0]['logical_key'])
 def test_kickoff_guard(self):
  self.assertEqual(len(self.call(now=self.kick)[0]),0)
 def test_team_guard(self):
  self.assertEqual(len(self.call(abbr={'1':'BUF'})[0]),0)
 def test_duplicate_week_guard(self):
  self.assertEqual(len(self.call(rows=self.rows+[self.rows[0]])[0]),0)
 def test_future_row_guard(self):
  self.assertEqual(len(self.call(rows=[dict(r,is_future='true') for r in self.rows])[0]),0)
 def test_unmapped_guard(self):
  self.assertEqual(len(self.call(crosswalk={})[0]),0)
 def test_no_write_calls(self):
  import inspect,phase3d37h_full_manifest
  src=inspect.getsource(phase3d37h_full_manifest)
  self.assertNotIn('requests.post(',src);self.assertNotIn('requests.patch(',src);self.assertNotIn('requests.delete(',src)
if __name__=='__main__':unittest.main()


class TestManifestTestBoundary(unittest.TestCase):
    def test_production_repository_rejected_before_any_fetch(self):
        from unittest.mock import patch
        from phase3d37h_full_manifest import main
        with patch('phase3d37h_full_manifest.fetch') as fetcher, patch.dict('os.environ', {'GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays','SUPABASE_URL':'https://luxezjthznupdghmexyh.supabase.co'}):
            with self.assertRaisesRegex(ValueError,'TEST GitHub repository'):
                main([])
            fetcher.assert_not_called()

    def test_production_project_rejected_before_any_fetch(self):
        from unittest.mock import patch
        from phase3d37h_full_manifest import main
        with patch('phase3d37h_full_manifest.fetch') as fetcher, patch.dict('os.environ', {'GITHUB_REPOSITORY':'dlindeman333/NFL_Parlays_Test','SUPABASE_URL':'https://wpvuunwtyxycqfjwuzkn.supabase.co'}):
            with self.assertRaisesRegex(ValueError,'TEST project'):
                main([])
            fetcher.assert_not_called()
