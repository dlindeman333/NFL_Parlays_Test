import unittest
from unittest.mock import patch
from phase3d32_snapshot_audit import audit
class TestAudit(unittest.TestCase):
    @patch('phase3d32_snapshot_audit.get_page')
    def test_empty(self,m):
        m.return_value=([],0)
        self.assertEqual(audit('https://example.supabase.co','key','nfl_prediction_grades')['row_count'],0)
    @patch('phase3d32_snapshot_audit.get_page')
    def test_pagination_and_fields(self,m):
        m.side_effect=[([{'id':1,'created_at':'2026-01-01'}],2),([{'id':2,'created_at':'2026-02-01'}],2)]
        result=audit('https://example.supabase.co','key','nfl_prediction_snapshots')
        self.assertEqual(result['row_count'],2)
        self.assertEqual(result['timestamp_bounds']['created_at']['latest'],'2026-02-01')
    @patch('phase3d32_snapshot_audit.get_page')
    def test_mutating_count_fails(self,m):
        m.side_effect=[([{'id':1}],2),([{'id':2}],3)]
        with self.assertRaises(ValueError):audit('https://example.supabase.co','key','nfl_prediction_snapshots')
if __name__=='__main__':unittest.main()
