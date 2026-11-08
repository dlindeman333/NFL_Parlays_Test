import hashlib, json, tempfile, unittest
from pathlib import Path
from nfl_package13_backup import backup, fetch_all, TABLES
class BackupTests(unittest.TestCase):
 def test_pagination(self):
  calls=[]
  def fetch(t,q):
   calls.append(int(q['offset']));return [{'n':i} for i in range(int(q['offset']),min(int(q['offset'])+2,5))]
  self.assertEqual(len(fetch_all(fetch,'test',2)),5)
  self.assertEqual(calls,[0,2,4])
 def test_full_backup_hashes(self):
  with tempfile.TemporaryDirectory() as d:
   manifest=backup(lambda t,q:[{'id':t,'value':1}],d)
   self.assertEqual(set(manifest['tables']),set(TABLES))
   self.assertFalse(manifest['restore_verified'])
   for t in TABLES:
    raw=(Path(d)/(t+'.json')).read_bytes()
    self.assertEqual(hashlib.sha256(raw).hexdigest(),manifest['tables'][t]['sha256'])
 def test_empty_tables(self):
  with tempfile.TemporaryDirectory() as d:
   m=backup(lambda t,q:[],d)
   self.assertTrue(all(x['rows']==0 for x in m['tables'].values()))
 def test_no_write_methods(self):
  import inspect,nfl_package13_backup
  s=inspect.getsource(nfl_package13_backup)
  self.assertNotIn('method=\'POST\'',s)
  self.assertNotIn('method=\'DELETE\'',s)
if __name__=='__main__':unittest.main()
