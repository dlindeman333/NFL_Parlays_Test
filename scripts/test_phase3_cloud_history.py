from pathlib import Path
import unittest

HTML=(Path(__file__).resolve().parents[1]/'index.html')
class CloudHistory(unittest.TestCase):
 def test_history_panel_and_owner_scoped_read(self):
  html=HTML.read_text()
  self.assertIn('id="cloudUserPredictionHistory"',html)
  self.assertIn('nfl_user_prediction_tracking?select=user_id,tracking_id,payload,updated_at&user_id=eq.',html)
  self.assertIn('rows.some(r=>r.user_id!==uid)',html)
  self.assertIn('const uid=await userId()',html)
 def test_no_history_writes(self):
  html=HTML.read_text()
  code=html.split('/* Phase 3 authenticated, owner-scoped cloud prediction history preview.')[1].split('</script>')[0]
  for marker in ("method:'POST'","method:'PATCH'","method:'DELETE'",'localStorage.setItem'):
   self.assertNotIn(marker,code)
if __name__=='__main__':unittest.main()
