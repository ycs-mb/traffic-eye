"""Traffic signal color classification using HSV analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from src.models import SignalState

logger = logging.getLogger(__name__)


@dataclass
class HSVRange:
    """HSV color range for detection."""
    h_low: int
    h_high: int
    s_low: int = 100
    s_high: int = 255
    v_low: int = 100
    v_high: int = 255


# Default HSV ranges for traffic signal colors
DEFAULT_SIGNAL_RANGES: dict[SignalState, list[HSVRange]] = {
    SignalState.RED: [
        HSVRange(h_low=0, h_high=10),    # Red wraps around 0
        HSVRange(h_low=170, h_high=180),
    ],
    SignalState.YELLOW: [
        HSVRange(h_low=15, h_high=35),
    ],
    SignalState.GREEN: [
        HSVRange(h_low=40, h_high=90),
    ],
}


class TrafficSignalClassifier:
    """Classifies traffic signal color from a cropped image using HSV analysis.

    Applies a circular mask (traffic lights are circular) to reduce noise
    from the signal housing.
    """

    def __init__(
        self,
        signal_ranges: Optional[dict[SignalState, list[HSVRange]]] = None,
        min_crop_size: int = 10,
        min_pixel_ratio: float = 0.05,
    ):
        """
        Args:
            signal_ranges: Custom HSV ranges per signal state.
            min_crop_size: Minimum width/height of crop to classify.
            min_pixel_ratio: Minimum ratio of colored pixels to total pixels
                            for a color to be considered dominant.
        """
        self._ranges = signal_ranges or DEFAULT_SIGNAL_RANGES
        self._min_crop_size = min_crop_size
        self._min_pixel_ratio = min_pixel_ratio

    def classify(self, signal_crop: np.ndarray) -> SignalState:
        """Classify the color of a traffic signal crop.

        Args:
            signal_crop: BGR image of a cropped traffic signal.

        Returns:
            SignalState enum value.
        """
        h, w = signal_crop.shape[:2]

        # Reject tiny crops
        if h < self._min_crop_size or w < self._min_crop_size:
            return SignalState.UNKNOWN

        # Apply circular mask
        masked = self._apply_circular_mask(signal_crop)

        # Convert to HSV
        hsv = cv2.cvtColor(masked, cv2.COLOR_BGR2HSV)

        # Count pixels for each color
        total_pixels = h * w
        color_counts: dict[SignalState, int] = {}

        for state, ranges in self._ranges.items():
            count = 0
            for r in ranges:
                lower = np.array([r.h_low, r.s_low, r.v_low])
                upper = np.array([r.h_high, r.s_high, r.v_high])
                mask = cv2.inRange(hsv, lower, upper)
                count += cv2.countNonZero(mask)
            color_counts[state] = count

        # Find dominant color
        if not color_counts:
            return SignalState.UNKNOWN

        best_state = max(color_counts, key=color_counts.get)
        best_ratio = color_counts[best_state] / total_pixels

        if best_ratio < self._min_pixel_ratio:
            return SignalState.UNKNOWN

        return best_state

    @staticmethod
    def _apply_circular_mask(image: np.ndarray) -> np.ndarray:
        """Apply a circular mask centered on the image."""
        h, w = image.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, h // 2)
        radius = min(w, h) // 2
        cv2.circle(mask, center, radius, 255, -1)
        return cv2.bitwise_and(image, image, mask=mask)
