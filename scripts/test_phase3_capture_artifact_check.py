import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from phase3_capture_artifact_check import check_directory
from phase3_forecast_snapshot import canonical

class CaptureCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = {'classification': 'MODEL_BASELINE_NOT_SPORTSBOOK_PICK', 'forecasts': [{'logical_key':'a'}], 'forecast_count': 1, 'database_writes':0, 'betting_picks_created':0, 'provenance_status':'UPSTREAM_PUBLICATION_NOT_INDEPENDENTLY_VERIFIED'}

    def save(self):
        digest = hashlib.sha256(canonical(self.payload)).hexdigest()
        (self.root / f'forecast-2026-week10-{digest[:16]}.json').write_text(json.dumps({'payload':self.payload, 'payload_sha256':digest}))

    def test_valid(self):
        self.save()
        self.assertEqual(check_directory(self.root), 1)

    def test_tamper(self):
        self.save()
        path = next(self.root.iterdir())
        obj = json.loads(path.read_text())
        obj['payload']['forecast_count'] = 5
        path.write_text(json.dumps(obj))
        with self.assertRaises(ValueError): check_directory(self.root)

    def test_duplicate(self):
        self.payload['forecasts'].append({'logical_key':'a'})
        self.payload['forecast_count'] = 2
        self.save()
        with self.assertRaises(ValueError): check_directory(self.root)

    def test_no_artifact(self):
        with self.assertRaises(ValueError): check_directory(self.root)

    def test_false_provenance(self):
        self.payload['provenance_status'] = 'CERTIFIED'
        self.save()
        with self.assertRaises(ValueError): check_directory(self.root)

if __name__ == '__main__': unittest.main()
