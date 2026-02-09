"""Circular frame buffer for rolling window of recent frames."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BufferedFrame:
    """A frame stored in the circular buffer."""
    frame: np.ndarray
    frame_id: int
    timestamp: datetime


class CircularFrameBuffer:
    """Rolling window of N seconds of frames in memory.

    Stores frames at the processing rate (not raw camera fps)
    to keep memory usage manageable. At 720p and 8fps, 10 seconds
    uses ~210MB.

    Uses a deque for O(1) push/pop operations.
    """

    def __init__(self, max_seconds: float, fps: float, max_frames: Optional[int] = None):
        """
        Args:
            max_seconds: Maximum duration of frames to keep.
            fps: Expected frame rate (used to calculate max_frames if not provided).
            max_frames: Override for max number of frames to store.
        """
        self._max_seconds = max_seconds
        self._fps = fps
        self._max_frames = max_frames or int(max_seconds * fps)
        self._buffer: deque[BufferedFrame] = deque(maxlen=self._max_frames)
        logger.info(
            "Frame buffer initialized: %.1fs window, %d max frames",
            max_seconds, self._max_frames,
        )

    def push(self, frame: np.ndarray, timestamp: datetime, frame_id: int) -> None:
        """Add a frame to the buffer. Oldest frame is dropped if buffer is full."""
        self._buffer.append(BufferedFrame(
            frame=frame.copy(),
            frame_id=frame_id,
            timestamp=timestamp,
        ))

    def get_clip(self, start_time: datetime, end_time: datetime) -> list[BufferedFrame]:
        """Get frames within a time range."""
        return [
            bf for bf in self._buffer
            if start_time <= bf.timestamp <= end_time
        ]

    def get_recent(self, seconds: float) -> list[BufferedFrame]:
        """Get frames from the last N seconds."""
        if not self._buffer:
            return []
        latest = self._buffer[-1].timestamp
        cutoff = latest - timedelta(seconds=seconds)
        return [bf for bf in self._buffer if bf.timestamp >= cutoff]

    def get_all(self) -> list[BufferedFrame]:
        """Get all frames currently in the buffer."""
        return list(self._buffer)

    def clear(self) -> None:
        """Clear all frames from the buffer."""
        self._buffer.clear()

    @property
    def is_full(self) -> bool:
        return len(self._buffer) >= self._max_frames

    @property
    def size(self) -> int:
        return len(self._buffer)

    @property
    def max_frames(self) -> int:
        return self._max_frames

    @property
    def memory_usage_bytes(self) -> int:
        """Estimate current memory usage of stored frames."""
        if not self._buffer:
            return 0
        return sum(bf.frame.nbytes for bf in self._buffer)
