import datetime as dt,unittest
from phase3d36_live_processing import parse_injuries,parse_games,match,validate_supabase_url
NOW=dt.datetime(2026,11,8,tzinfo=dt.timezone.utc)
class TestLiveProcessing(unittest.TestCase):
 def test_injury_candidate(self):
  feed={'injuries':[{'id':'2','injuries':[{'athlete':{'id':'123','displayName':'Example'},'status':'Questionable','date':'2026-11-07T12:00:00Z'}]}]}
  rows=parse_injuries(feed,NOW);self.assertTrue(rows[0]['eligible_evidence']);self.assertEqual(rows[0]['team'],'BUF')
 def test_stale_hold(self):
  feed={'injuries':[{'id':'2','injuries':[{'athlete':{'id':'123'},'status':'Out','date':'2026-10-01T12:00:00Z'}]}]}
  self.assertEqual(parse_injuries(feed,NOW)[0]['hold_reason'],'stale_or_future')
 def test_schedule_matching(self):
  games=parse_games({'events':[{'id':'100','date':'2026-11-09T20:00:00Z','competitions':[{'competitors':[{'homeAway':'home','team':{'abbreviation':'BUF'}},{'homeAway':'away','team':{'abbreviation':'MIA'}}]}]}]},NOW)
  self.assertEqual(match([{'player_id':'123','team':'BUF','status':'Out','source_updated_at':'x','hold_reason':None}],games)[0]['decision'],'REVIEW_ONLY')
  self.assertFalse(games[0]['kickoff_independently_verified'])
 def test_missing_player_hold(self):
  rows=parse_injuries({'injuries':[{'id':'2','injuries':[{'athlete':{},'status':'Out','date':'2026-11-07T12:00:00Z'}]}]},NOW)
  self.assertEqual(rows[0]['hold_reason'],'missing_player_id')
 def test_invalid_supabase(self):
  with self.assertRaises(ValueError):validate_supabase_url('http://evil.test')
if __name__=='__main__':unittest.main()
