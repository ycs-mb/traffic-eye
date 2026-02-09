"""Confidence aggregation and threshold routing."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ConfidenceAggregator:
    """Aggregates confidence scores across detection stages.

    Final confidence = weighted combination of:
    - Object detection confidence (default weight: 0.3)
    - Classification confidence (default weight: 0.3)
    - Temporal consistency ratio (default weight: 0.2)
    - OCR confidence, if available (default weight: 0.2)

    When OCR confidence is not available, its weight is redistributed
    proportionally among other components.
    """

    DEFAULT_WEIGHTS = {
        "detection": 0.3,
        "classification": 0.3,
        "temporal": 0.2,
        "ocr": 0.2,
    }

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self._weights = weights or self.DEFAULT_WEIGHTS.copy()

    def compute(
        self,
        detection_conf: float,
        classification_conf: float,
        temporal_ratio: float,
        ocr_conf: Optional[float] = None,
    ) -> float:
        """Compute aggregated confidence score.

        Args:
            detection_conf: Object detection confidence [0, 1].
            classification_conf: Helmet/signal classification confidence [0, 1].
            temporal_ratio: Ratio of consecutive frames to required minimum [0, 1+].
            ocr_conf: License plate OCR confidence, or None if unavailable.

        Returns:
            Aggregated confidence score [0, 1].
        """
        temporal_clamped = min(1.0, max(0.0, temporal_ratio))

        scores = {
            "detection": detection_conf,
            "classification": classification_conf,
            "temporal": temporal_clamped,
        }

        if ocr_conf is not None:
            scores["ocr"] = ocr_conf
            active_weights = {k: self._weights[k] for k in scores}
        else:
            # Redistribute OCR weight proportionally
            active_weights = {k: self._weights[k] for k in scores}
            total_active = sum(active_weights.values())
            if total_active > 0:
                scale = 1.0 / total_active
                active_weights = {k: v * scale for k, v in active_weights.items()}

        # Weighted sum
        result = sum(
            scores[k] * active_weights.get(k, 0.0)
            for k in scores
        )

        return max(0.0, min(1.0, result))

    @staticmethod
    def meets_local_threshold(confidence: float, threshold: float = 0.96) -> bool:
        """Check if confidence is high enough for local processing."""
        return confidence >= threshold

    @staticmethod
    def needs_cloud_verification(confidence: float, low: float = 0.70, high: float = 0.96) -> bool:
        """Check if confidence falls in the cloud verification range."""
        return low <= confidence < high

    @staticmethod
    def should_discard(confidence: float, threshold: float = 0.70) -> bool:
        """Check if confidence is too low to pursue."""
        return confidence < threshold
