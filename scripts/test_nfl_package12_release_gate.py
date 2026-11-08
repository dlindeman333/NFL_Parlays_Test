import unittest
from nfl_package12_release_gate import evaluate

class GateTests(unittest.TestCase):
    def fixture(self):
        return {'season':2026,'week':9,'snapshot_count':1,'grade_plan':{'candidates':[{'season':2026,'week':9,'game_id':'1','pick_index':0,'grade':'HIT','pick_sha256':'a'*64}], 'blocked_reasons':{}}}
    def test_blocks_writes(self):
        r=evaluate(self.fixture(),[{'season':2026,'week':9,'game_id':'1','pick':'x'}])
        self.assertFalse(r['activation_allowed']);self.assertEqual(r['grade_writes'],0)
    def test_empty_grade_table(self):
        self.assertTrue(any('empty' in x for x in evaluate(self.fixture(),[])['blockers']))
    def test_duplicate_rejected(self):
        f=self.fixture();f['grade_plan']['candidates']*=2
        with self.assertRaises(ValueError):evaluate(f,[])
    def test_invalid_grade_rejected(self):
        f=self.fixture();f['grade_plan']['candidates'][0]['grade']='UNAVAILABLE'
        with self.assertRaises(ValueError):evaluate(f,[])
    def test_manifest_stable(self):
        self.assertEqual(evaluate(self.fixture(),[])['candidate_manifest_sha256'],evaluate(self.fixture(),[])['candidate_manifest_sha256'])
if __name__=='__main__':unittest.main()
