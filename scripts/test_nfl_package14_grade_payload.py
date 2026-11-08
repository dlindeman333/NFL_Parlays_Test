import unittest
from nfl_package14_grade_payload import stage

C={'season':2026,'week':9,'game_id':'g','pick_index':0,'pick_sha256':'a'*64,'grade':'HIT','evidence':{}}
class TestStage(unittest.TestCase):
 def test_fail_closed_without_key(self):
  r=stage({'candidates':[C]});self.assertEqual(r['staged_count'],0);self.assertEqual(r['blocked'][0]['reason'],'PICK_KEY_CONTRACT_NOT_VERIFIED')
 def test_known_key_preview(self):
  r=stage({'candidates':[C]},key_resolver=lambda c:'verified-key');self.assertEqual(r['payloads'][0]['pick_key'],'verified-key');self.assertFalse(r['activation_allowed'])
 def test_existing_not_overwritten(self):
  r=stage({'candidates':[C]},key_resolver=lambda c:'key',existing_keys={(2026,9,'g','key')});self.assertEqual(r['staged_count'],0)
 def test_duplicate_rejected(self):
  with self.assertRaises(ValueError):stage({'candidates':[C,C]})
 def test_bad_grade_rejected(self):
  with self.assertRaises(ValueError):stage({'candidates':[dict(C,grade='PENDING')]})
 def test_bad_actual_rejected(self):
  r=stage({'candidates':[dict(C,evidence={'actual_value':'bad'})]},key_resolver=lambda c:'key');self.assertEqual(r['staged_count'],0)
if __name__=='__main__':unittest.main()
