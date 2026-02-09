"""Temporal consistency checking for violation detection."""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class TemporalConsistencyChecker:
    """Tracks whether a violation condition persists across N consecutive frames.

    Uses (violation_type, track_id) as the key to associate detections
    across frames. A violation is only confirmed when the condition holds
    for min_consecutive_frames in a row for the SAME tracked object.
    """

    def __init__(self):
        # (violation_type, track_id) -> consecutive count
        self._counters: dict[tuple[str, int], int] = defaultdict(int)

    def update(
        self,
        violation_type: str,
        track_id: int,
        condition_met: bool,
        min_frames: int,
    ) -> bool:
        """Update the consistency counter and check if threshold is met.

        Args:
            violation_type: Type of violation being checked.
            track_id: Track ID of the object being evaluated.
            condition_met: Whether the violation condition was met this frame.
            min_frames: Minimum consecutive frames required.

        Returns:
            True if the condition has been met for min_frames consecutive frames.
        """
        key = (violation_type, track_id)

        if condition_met:
            self._counters[key] += 1
        else:
            self._counters[key] = 0

        return self._counters[key] >= min_frames

    def get_count(self, violation_type: str, track_id: int) -> int:
        """Get current consecutive frame count."""
        return self._counters.get((violation_type, track_id), 0)

    def reset(self, violation_type: str, track_id: int) -> None:
        """Reset counter for a specific violation+track pair."""
        key = (violation_type, track_id)
        self._counters.pop(key, None)

    def reset_all(self) -> None:
        """Reset all counters."""
        self._counters.clear()

    def cleanup_stale(self, active_track_ids: set[int]) -> None:
        """Remove counters for tracks that no longer exist."""
        stale_keys = [
            k for k in self._counters
            if k[1] not in active_track_ids
        ]
        for key in stale_keys:
            del self._counters[key]
