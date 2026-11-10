import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from phase3_postgame_artifact_pipeline import produce


class TestPostgameArtifactPipeline(unittest.TestCase):
    def test_no_inputs_fail_closed_and_report_only(self):
        with tempfile.TemporaryDirectory() as temp:
            result = produce(output_dir=temp)
            self.assertFalse(result['ready'])
            self.assertEqual(result['database_writes'], 0)
            self.assertTrue((Path(temp) / 'postgame-grading-readiness.json').exists())
            self.assertFalse((Path(temp) / 'phase3-grade-export.json').exists())

    def test_validated_input_creates_offline_export(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('phase3_postgame_artifact_pipeline.run', return_value={'ready': True, 'database_writes': 0}):
                with patch('phase3_postgame_artifact_pipeline.build_export', return_value={'ready': True, 'database_writes': 0, 'rows': [{'tracking_id': 'x'}]}):
                    result = produce('snapshots.json', 'stats.csv', temp)
            self.assertEqual(result['exported_rows'], 1)
            self.assertEqual(json.loads((Path(temp) / 'phase3-grade-export.json').read_text())['database_writes'], 0)

    def test_rejects_export_that_claims_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('phase3_postgame_artifact_pipeline.run', return_value={'ready': True, 'database_writes': 0}):
                with patch('phase3_postgame_artifact_pipeline.build_export', return_value={'ready': True, 'database_writes': 1, 'rows': []}):
                    with self.assertRaisesRegex(ValueError, 'offline contract'):
                        produce('a', 'b', temp)
                    self.assertFalse((Path(temp) / 'phase3-grade-export.json').exists())
