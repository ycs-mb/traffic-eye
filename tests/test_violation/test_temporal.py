"""Tests for temporal consistency checker."""

from src.violation.temporal import TemporalConsistencyChecker


class TestTemporalConsistencyChecker:
    def test_not_met_below_threshold(self):
        checker = TemporalConsistencyChecker()
        assert checker.update("no_helmet", 1, True, 3) is False
        assert checker.update("no_helmet", 1, True, 3) is False

    def test_met_at_threshold(self):
        checker = TemporalConsistencyChecker()
        checker.update("no_helmet", 1, True, 3)
        checker.update("no_helmet", 1, True, 3)
        assert checker.update("no_helmet", 1, True, 3) is True

    def test_reset_on_false(self):
        checker = TemporalConsistencyChecker()
        checker.update("no_helmet", 1, True, 3)
        checker.update("no_helmet", 1, True, 3)
        checker.update("no_helmet", 1, False, 3)  # Reset
        assert checker.get_count("no_helmet", 1) == 0

    def test_separate_tracks(self):
        checker = TemporalConsistencyChecker()
        checker.update("no_helmet", 1, True, 2)
        checker.update("no_helmet", 2, True, 2)
        # Track 1 has 1 frame, track 2 has 1 frame
        assert checker.get_count("no_helmet", 1) == 1
        assert checker.get_count("no_helmet", 2) == 1

    def test_separate_violation_types(self):
        checker = TemporalConsistencyChecker()
        checker.update("no_helmet", 1, True, 2)
        checker.update("red_light_jump", 1, True, 2)
        assert checker.get_count("no_helmet", 1) == 1
        assert checker.get_count("red_light_jump", 1) == 1

    def test_reset_specific(self):
        checker = TemporalConsistencyChecker()
        checker.update("no_helmet", 1, True, 5)
        checker.update("no_helmet", 2, True, 5)
        checker.reset("no_helmet", 1)
        assert checker.get_count("no_helmet", 1) == 0
        assert checker.get_count("no_helmet", 2) == 1

    def test_reset_all(self):
        checker = TemporalConsistencyChecker()
        checker.update("no_helmet", 1, True, 5)
        checker.update("red_light_jump", 2, True, 5)
        checker.reset_all()
        assert checker.get_count("no_helmet", 1) == 0
        assert checker.get_count("red_light_jump", 2) == 0

    def test_cleanup_stale(self):
        checker = TemporalConsistencyChecker()
        checker.update("no_helmet", 1, True, 5)
        checker.update("no_helmet", 2, True, 5)
        checker.cleanup_stale(active_track_ids={2})
        assert checker.get_count("no_helmet", 1) == 0
        assert checker.get_count("no_helmet", 2) == 1
