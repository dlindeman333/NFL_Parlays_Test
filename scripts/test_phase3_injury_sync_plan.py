import unittest
from datetime import datetime, timezone
from phase3_injury_sync_plan import build_sync_plan

NOW = datetime(2026, 11, 9, 20, tzinfo=timezone.utc)

def item(player='1', status='OUT', observed='2026-11-09T19:00:00Z'):
    return dict(player_id=player, team='BUF', source='team-report', status=status, observed_at=observed)

class InjurySyncPlanTests(unittest.TestCase):
    def plan(self, new=None, old=None, complete=True):
        return build_sync_plan([item()] if new is None else new, [] if old is None else old,
                               now=NOW, feed_complete=complete)
    def test_blocks_unverified_feed(self):
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.plan(complete=False)
    def test_blocks_empty_feed(self):
        with self.assertRaisesRegex(ValueError, 'empty'):
            self.plan(new=[])
    def test_new_record_proposed_no_writes(self):
        result = self.plan()
        self.assertEqual(len(result['proposed_upserts']), 1)
        self.assertFalse(result['cloud_writes_enabled'])
        self.assertEqual(result['proposed_deletes'], [])
    def test_identical_record_unchanged(self):
        result = self.plan(old=[item(observed='2026-11-09T19:00:00+00:00')])
        self.assertEqual(result['unchanged'], 1)
        self.assertEqual(result['proposed_upserts'], [])
    def test_equivalent_zulu_timestamp_does_not_trigger_upsert(self):
        result = self.plan(old=[item(observed='2026-11-09T19:00:00Z')])
        self.assertEqual(result['unchanged'], 1)
        self.assertEqual(result['proposed_upserts'], [])
    def test_equivalent_offset_timestamp_does_not_trigger_upsert(self):
        result = self.plan(old=[item(observed='2026-11-09T14:00:00-05:00')])
        self.assertEqual(result['unchanged'], 1)
        self.assertEqual(result['proposed_upserts'], [])
    def test_naive_prior_timestamp_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            self.plan(old=[item(observed='2026-11-09T19:00:00')])
    def test_invalid_existing_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'status'):
            self.plan(old=[item(status='UNKNOWN')])
    def test_older_observation_does_not_override(self):
        result = self.plan(old=[item(status='QUESTIONABLE', observed='2026-11-09T19:30:00Z')])
        self.assertEqual(result['older_than_stored_skipped'], 1)
        self.assertEqual(result['proposed_upserts'], [])
    def test_missing_prior_player_is_not_cleared(self):
        result = self.plan(old=[item(player='2')])
        self.assertEqual(result['previously_stored_not_in_feed_preserved'], 1)
        self.assertEqual(result['proposed_deletes'], [])
    def test_changed_status_proposed(self):
        result = self.plan(old=[item(status='QUESTIONABLE', observed='2026-11-09T18:00:00Z')])
        self.assertEqual(result['proposed_upserts'][0]['status'], 'OUT')
    def test_equal_timestamp_conflicting_status_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'conflicting injury observation'):
            self.plan(old=[item(status='QUESTIONABLE')])
    def test_equal_timestamp_conflicting_source_fails_closed(self):
        previous = item()
        previous['source'] = 'different-report'
        with self.assertRaisesRegex(ValueError, 'conflicting injury observation'):
            self.plan(old=[previous])
    def test_newer_status_update_remains_allowed(self):
        result = self.plan(old=[item(status='QUESTIONABLE', observed='2026-11-09T18:59:00Z')])
        self.assertEqual(len(result['proposed_upserts']), 1)
    def test_invalid_existing_timestamp_fails(self):
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            self.plan(old=[item(observed='bad')])
    def test_future_dated_existing_record_blocks_sync(self):
        with self.assertRaisesRegex(ValueError, 'future-dated'):
            self.plan(old=[item(observed='2026-11-10T20:00:00Z')])
    def test_future_dated_existing_record_blocks_even_if_not_in_feed(self):
        with self.assertRaisesRegex(ValueError, 'future-dated'):
            self.plan(old=[item(player='other', observed='2026-11-10T20:00:00Z')])
    def test_naive_current_time_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'now must include timezone'):
            build_sync_plan([item()], [], now=datetime(2026, 11, 9, 20), feed_complete=True)
    def test_whitespace_stored_player_id_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'noncanonical existing injury identity'):
            self.plan(old=[item(player=' 1 ')])
    def test_whitespace_stored_team_fails_closed(self):
        previous = item()
        previous['team'] = ' BUF '
        with self.assertRaisesRegex(ValueError, 'noncanonical existing injury identity'):
            self.plan(old=[previous])
    def test_duplicate_feed_fails(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.plan(new=[item(), item()])

if __name__ == '__main__':
    unittest.main()
