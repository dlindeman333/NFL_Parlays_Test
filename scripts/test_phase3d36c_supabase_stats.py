import unittest
from phase3d36c_supabase_stats import analyze_export, validate_project_url

class Tests(unittest.TestCase):
    def test_url(self):
        self.assertTrue(validate_project_url('https://abc.supabase.co'))
        self.assertFalse(validate_project_url('https://example.com'))
    def test_missing(self):
        self.assertEqual(analyze_export({'csv_text':'name,team\nA,BUF\n'})['status'],'missing_columns')
    def test_empty(self):
        self.assertEqual(analyze_export(None)['status'],'no_export_for_season')
    def test_valid(self):
        s='season,week,player_id,name,team,next_opponent,games_played_to_date,pass_yards_last3_avg,pass_yards_season_avg\n2026,10,12,Sample,BUF,MIA,5,250,200\n'
        r=analyze_export({'csv_text':s},2026)
        self.assertEqual(r['eligible_unique_players'],1)
        self.assertEqual(r['candidates'][0]['projections'][0]['projection'],230.0)

if __name__=='__main__': unittest.main()
