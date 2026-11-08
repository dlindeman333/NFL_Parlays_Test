import hashlib
import json
import pathlib
import tempfile
import unittest
from nfl_backup_rehearsal import EXPECTED,rehearse

class BackupRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.temp.name)
        self.manifest={'mode':'READ_ONLY_LOGICAL_BACKUP','tables':{}}
        for t in EXPECTED:
            raw=json.dumps([{'id':'test','nested':{'a':[1,2]}}],sort_keys=True,separators=(',',':')).encode()
            (self.root/(t+'.json')).write_bytes(raw)
            self.manifest['tables'][t]={'rows':1,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):(self.root/'manifest.json').write_text(json.dumps(self.manifest))
    def test_roundtrip(self):
        result=rehearse(self.root)
        self.assertEqual(result['result'],'PASS')
        self.assertFalse(result['supabase_restore_verified'])
    def test_tamper_rejected(self):
        with (self.root/(EXPECTED[0]+'.json')).open('ab') as f:f.write(b' ')
        with self.assertRaisesRegex(ValueError,'integrity'):rehearse(self.root)
    def test_missing_table_rejected(self):
        del self.manifest['tables'][EXPECTED[0]];self.save()
        with self.assertRaisesRegex(ValueError,'table list'):rehearse(self.root)
    def test_count_mismatch_rejected(self):
        self.manifest['tables'][EXPECTED[0]]['rows']=2;self.save()
        with self.assertRaisesRegex(ValueError,'record mismatch'):rehearse(self.root)
if __name__=='__main__':unittest.main()
