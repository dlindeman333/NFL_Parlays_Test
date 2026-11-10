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

    def test_blocked_run_removes_stale_export(self):
        with tempfile.TemporaryDirectory() as temp:
            stale = Path(temp) / 'phase3-grade-export.json'
            stale.write_text('{"ready": true}')
            result = produce(output_dir=temp)
            self.assertFalse(result['ready'])
            self.assertFalse(stale.exists())

    def test_invalid_new_export_cannot_leave_old_success(self):
        with tempfile.TemporaryDirectory() as temp:
            stale = Path(temp) / 'phase3-grade-export.json'
            stale.write_text('{"ready": true}')
            with patch('phase3_postgame_artifact_pipeline.run', return_value={'ready': True, 'database_writes': 0}):
                with patch('phase3_postgame_artifact_pipeline.build_export', return_value={'ready': True, 'database_writes': 1, 'rows': []}):
                    with self.assertRaisesRegex(ValueError, 'offline contract'):
                        produce('a', 'b', temp)
            self.assertFalse(stale.exists())

    def test_export_serialization_failure_leaves_no_partial_success(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('phase3_postgame_artifact_pipeline.run', return_value={'ready': True, 'database_writes': 0}):
                with patch('phase3_postgame_artifact_pipeline.build_export', return_value={'ready': True, 'database_writes': 0, 'rows': [set([1])]}):
                    with self.assertRaises(TypeError):
                        produce('snapshots', 'stats', temp)
            self.assertFalse((Path(temp) / 'phase3-grade-export.json').exists())
            self.assertEqual(list(Path(temp).glob('.grade-export-*.tmp')), [])

    def test_atomic_publish_failure_cleans_temp_and_stale_export(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'phase3-grade-export.json').write_text('old success')
            with patch('phase3_postgame_artifact_pipeline.run', return_value={'ready': True, 'database_writes': 0}):
                with patch('phase3_postgame_artifact_pipeline.build_export', return_value={'ready': True, 'database_writes': 0, 'rows': []}):
                    with patch('phase3_postgame_artifact_pipeline.os.replace', side_effect=OSError('simulated disk error')):
                        with self.assertRaisesRegex(OSError, 'simulated disk error'):
                            produce('snapshots', 'stats', temp)
            self.assertFalse((Path(temp) / 'phase3-grade-export.json').exists())
            self.assertEqual(list(Path(temp).glob('.grade-export-*.tmp')), [])

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
