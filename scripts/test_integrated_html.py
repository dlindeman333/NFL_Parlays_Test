from pathlib import Path
import unittest
class AppIntegration(unittest.TestCase):
 def test_read_only_cloud_panel(self):
  html=(Path(__file__).resolve().parents[1]/'index.html').read_text()
  for s in ('id="cloudOfficialGrades"','nfl_prediction_grades?select=','Official cloud grading','nfl_prediction_snapshots','nflp-cloud-'):
   self.assertIn(s,html)
  cloud=html.split('/* Phase 3 official grade display:')[1].split('</script>')[0]
  self.assertNotIn("method:'POST'",cloud)
  self.assertNotIn("method:'PATCH'",cloud)
  self.assertNotIn("method:'DELETE'",cloud)
if __name__=='__main__':unittest.main()
