import importlib.util, pathlib, unittest
spec=importlib.util.spec_from_file_location('audit',pathlib.Path(__file__).with_name('phase3d37k_pick_compat_audit.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
class Tests(unittest.TestCase):
 def test_list_shape(self):
  r=audit.describe_picks([{'pick_key':'a','line':5},{'pick_key':'b','line':6}]);self.assertEqual(r['length'],2);self.assertEqual(r['object_field_sets'][0]['count'],2)
 def test_dict_shape(self):self.assertEqual(audit.describe_picks({'x':{'foo':1}})['container'],'object')
 def test_null_shape(self):self.assertEqual(audit.describe_picks(None)['container'],'NoneType')
 def test_schema_reject(self):
  with self.assertRaises(ValueError):audit.analyze([{'picks':[]}])
 def test_no_pick_values_leaked(self):
  row=dict.fromkeys(audit.BASE_FIELDS);row.update(season=2026,week=9,game_id='1',model_version='v',kickoff_at='2026-11-08T10:00:00Z',created_at='2026-11-08T09:00:00Z',picks=[{'pick_key':'SECRET_ID','line':999}]);self.assertNotIn('SECRET_ID',str(audit.analyze([row])))
 def test_kickoff_check(self):self.assertTrue(audit._before('2026-11-08T09:00:00Z','2026-11-08T10:00:00Z'))
if __name__=='__main__':unittest.main()
