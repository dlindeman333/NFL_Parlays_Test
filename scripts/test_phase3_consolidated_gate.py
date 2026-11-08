import datetime as dt, hashlib, unittest
from phase3_consolidated_gate import evaluate

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,8,12,0,tzinfo=UTC)
RAW=b'fixture\n'; SHA=hashlib.sha256(RAW).hexdigest()

def fixture():
    m={'season':2026,'week':10,'source_sha256':SHA,'candidate_metrics':1,'source_freshness_blocker':False,
       'source_acquired_at_utc':'2026-11-08T11:00:00+00:00'}
    c=[{'game_id':'12345','espn_id':'1234','metric':'pass_yards','logical_key':'2026/10/12345/1234/pass_yards',
        'source_sha256':SHA,'baseline':210.5,'history_weeks':[7,8,9],
        'kickoff_at':'2026-11-09T18:00:00Z','position':'QB'}]
    return m,c

class TestGate(unittest.TestCase):
    def test_new_game_remains_blocked(self):
        m,c=fixture();r=evaluate(m,c,RAW,set(),NOW)
        self.assertEqual(r['new_game_plans'],1);self.assertEqual(r['database_writes'],0)
        self.assertEqual(r['betting_picks_created'],0);self.assertEqual(r['readiness'],'BLOCKED_FOR_WRITES')
    def test_existing_game_skipped(self):
        m,c=fixture();r=evaluate(m,c,RAW,{(2026,10,'12345')},NOW)
        self.assertEqual(r['existing_game_skips'],1)
    def test_hash_mismatch_rejected(self):
        m,c=fixture()
        with self.assertRaisesRegex(ValueError,'SOURCE_HASH_MISMATCH'):evaluate(m,c,b'wrong',set(),NOW)
    def test_duplicate_rejected(self):
        m,c=fixture();m['candidate_metrics']=2
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):evaluate(m,c+c,RAW,set(),NOW)
    def test_kickoff_rejected(self):
        m,c=fixture();c[0]['kickoff_at']='2026-11-08T12:05:00Z'
        with self.assertRaisesRegex(ValueError,'CANDIDATE_GATE_REJECTED'):evaluate(m,c,RAW,set(),NOW)
    def test_stale_capture_rejected(self):
        m,c=fixture();m['source_acquired_at_utc']='2026-11-07T11:00:00+00:00'
        with self.assertRaisesRegex(ValueError,'SOURCE_CAPTURE_TOO_OLD'):evaluate(m,c,RAW,set(),NOW)
    def test_stale_export_rejected(self):
        m,c=fixture();m['source_freshness_blocker']='stale'
        with self.assertRaisesRegex(ValueError,'STALE_SOURCE'):evaluate(m,c,RAW,set(),NOW)

if __name__=='__main__':unittest.main()
