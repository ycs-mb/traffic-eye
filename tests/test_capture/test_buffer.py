"""Tests for circular frame buffer."""

from datetime import datetime, timedelta, timezone

import numpy as np

from src.capture.buffer import CircularFrameBuffer


class TestCircularFrameBuffer:
    def test_push_and_size(self):
        buf = CircularFrameBuffer(max_seconds=5, fps=2)
        assert buf.size == 0
        assert buf.max_frames == 10

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        now = datetime.now(timezone.utc)
        buf.push(frame, now, 0)
        assert buf.size == 1

    def test_max_frames_eviction(self):
        buf = CircularFrameBuffer(max_seconds=1, fps=2, max_frames=3)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        now = datetime.now(timezone.utc)

        for i in range(5):
            buf.push(frame, now + timedelta(seconds=i), i)

        assert buf.size == 3
        assert buf.is_full

    def test_get_clip(self):
        buf = CircularFrameBuffer(max_seconds=10, fps=2)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(10):
            buf.push(frame, base + timedelta(seconds=i), i)

        clip = buf.get_clip(
            base + timedelta(seconds=3),
            base + timedelta(seconds=6),
        )
        assert len(clip) == 4  # frames at t=3,4,5,6
        assert clip[0].frame_id == 3
        assert clip[-1].frame_id == 6

    def test_get_recent(self):
        buf = CircularFrameBuffer(max_seconds=10, fps=2)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(10):
            buf.push(frame, base + timedelta(seconds=i), i)

        recent = buf.get_recent(3)
        assert len(recent) == 4  # frames at t=7,8,9 plus boundary at t=6

    def test_clear(self):
        buf = CircularFrameBuffer(max_seconds=5, fps=2)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        buf.push(frame, datetime.now(timezone.utc), 0)
        assert buf.size == 1
        buf.clear()
        assert buf.size == 0

    def test_memory_usage(self):
        buf = CircularFrameBuffer(max_seconds=5, fps=2)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        buf.push(frame, datetime.now(timezone.utc), 0)
        assert buf.memory_usage_bytes == 100 * 100 * 3

    def test_empty_get_recent(self):
        buf = CircularFrameBuffer(max_seconds=5, fps=2)
        assert buf.get_recent(3) == []

    def test_frame_copied(self):
        """Ensure pushed frame is copied, not referenced."""
        buf = CircularFrameBuffer(max_seconds=5, fps=2)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        buf.push(frame, datetime.now(timezone.utc), 0)
        frame[:] = 255  # Modify original
        stored = buf.get_all()
        assert stored[0].frame[0, 0, 0] == 0  # Buffer copy unaffected
