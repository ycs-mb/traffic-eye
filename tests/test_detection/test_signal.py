"""Tests for traffic signal HSV classifier."""

import numpy as np

from src.detection.signal import TrafficSignalClassifier
from src.models import SignalState


class TestTrafficSignalClassifier:
    def _make_color_crop(self, bgr_color, size=50):
        """Create a solid color image."""
        return np.full((size, size, 3), bgr_color, dtype=np.uint8)

    def test_red_signal(self):
        clf = TrafficSignalClassifier()
        # Red in BGR: (0, 0, 255)
        crop = self._make_color_crop([0, 0, 255])
        result = clf.classify(crop)
        assert result == SignalState.RED

    def test_green_signal(self):
        clf = TrafficSignalClassifier()
        # Green in BGR: (0, 255, 0)
        crop = self._make_color_crop([0, 255, 0])
        result = clf.classify(crop)
        assert result == SignalState.GREEN

    def test_yellow_signal(self):
        clf = TrafficSignalClassifier()
        # Yellow in BGR: (0, 255, 255)
        crop = self._make_color_crop([0, 255, 255])
        result = clf.classify(crop)
        assert result == SignalState.YELLOW

    def test_too_small_crop(self):
        clf = TrafficSignalClassifier(min_crop_size=20)
        crop = np.zeros((5, 5, 3), dtype=np.uint8)
        result = clf.classify(crop)
        assert result == SignalState.UNKNOWN

    def test_dark_image_unknown(self):
        clf = TrafficSignalClassifier()
        # Very dark image - no dominant color
        crop = np.full((50, 50, 3), 10, dtype=np.uint8)
        result = clf.classify(crop)
        assert result == SignalState.UNKNOWN
