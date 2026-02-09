"""Violation rule engine with configurable rules."""

from __future__ import annotations

import logging
import math
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from src.models import (
    BoundingBox,
    Detection,
    FrameData,
    GPSReading,
    SignalState,
    ViolationCandidate,
    ViolationType,
)
from src.violation.confidence import ConfidenceAggregator
from src.violation.temporal import TemporalConsistencyChecker

logger = logging.getLogger(__name__)


class ViolationRule(ABC):
    """Abstract base class for violation detection rules."""

    @property
    @abstractmethod
    def violation_type(self) -> ViolationType:
        """The type of violation this rule detects."""

    @abstractmethod
    def evaluate(
        self,
        frame_data: FrameData,
        context: dict,
    ) -> list[tuple[int, float]]:
        """Evaluate the rule for a frame.

        Args:
            frame_data: Current frame with detections.
            context: Additional context (signal state, GPS, etc.).

        Returns:
            List of (track_id, confidence) pairs for violations found.
        """


class NoHelmetRule(ViolationRule):
    """Detect motorcycle riders without helmets.

    Condition: motorcycle detected AND person on/near it AND no helmet.
    """

    def __init__(self, proximity_threshold: float = 0.3):
        """
        Args:
            proximity_threshold: IoU threshold for person-motorcycle association.
        """
        self._proximity_threshold = proximity_threshold

    @property
    def violation_type(self) -> ViolationType:
        return ViolationType.NO_HELMET

    def evaluate(
        self,
        frame_data: FrameData,
        context: dict,
    ) -> list[tuple[int, float]]:
        violations = []
        motorcycles = [d for d in frame_data.detections if d.bbox.class_name == "motorcycle"]
        persons = [d for d in frame_data.detections if d.bbox.class_name == "person"]
        helmet_classifier = context.get("helmet_classifier")

        for moto in motorcycles:
            for person in persons:
                # Check if person is near/on the motorcycle
                iou = moto.bbox.iou(person.bbox)
                if iou < self._proximity_threshold:
                    # Also check vertical overlap: person above motorcycle
                    if not self._person_on_motorcycle(person.bbox, moto.bbox):
                        continue

                # Check helmet status
                has_helmet = context.get("has_helmet", {}).get(
                    person.track_id, None
                )
                helmet_conf = context.get("helmet_confidence", {}).get(
                    person.track_id, 0.0
                )

                if has_helmet is False:
                    track_id = person.track_id or moto.track_id or 0
                    conf = min(moto.bbox.confidence, person.bbox.confidence, helmet_conf)
                    violations.append((track_id, conf))

        return violations

    @staticmethod
    def _person_on_motorcycle(person: BoundingBox, moto: BoundingBox) -> bool:
        """Check if person bounding box is positioned on/above motorcycle."""
        # Person's bottom should be near or overlap motorcycle's vertical range
        person_bottom = person.y2
        moto_top = moto.y1
        moto_bottom = moto.y2
        # Person should overlap horizontally
        h_overlap = min(person.x2, moto.x2) - max(person.x1, moto.x1)
        moto_width = moto.width
        if moto_width <= 0:
            return False
        return h_overlap > 0 and person_bottom >= moto_top and person.y1 < moto_bottom


class RedLightJumpRule(ViolationRule):
    """Detect vehicles crossing during a red signal."""

    @property
    def violation_type(self) -> ViolationType:
        return ViolationType.RED_LIGHT_JUMP

    def evaluate(
        self,
        frame_data: FrameData,
        context: dict,
    ) -> list[tuple[int, float]]:
        signal_state = context.get("signal_state", SignalState.UNKNOWN)
        if signal_state != SignalState.RED:
            return []

        violations = []
        vehicle_classes = {"car", "truck", "bus", "motorcycle"}
        vehicles = [
            d for d in frame_data.detections
            if d.bbox.class_name in vehicle_classes
        ]

        for vehicle in vehicles:
            # A simple heuristic: vehicle is in the lower portion of the frame
            # (suggesting it is at/crossing the stop line)
            frame_h = frame_data.height
            if vehicle.bbox.center[1] > frame_h * 0.5:
                track_id = vehicle.track_id or 0
                violations.append((track_id, vehicle.bbox.confidence))

        return violations


class WrongSideRule(ViolationRule):
    """Detect wrong-side driving using GPS heading deviation."""

    def __init__(self, heading_deviation_threshold: float = 120.0):
        self._threshold = heading_deviation_threshold

    @property
    def violation_type(self) -> ViolationType:
        return ViolationType.WRONG_SIDE

    def evaluate(
        self,
        frame_data: FrameData,
        context: dict,
    ) -> list[tuple[int, float]]:
        gps = frame_data.gps
        road_bearing = context.get("road_bearing")

        if gps is None or road_bearing is None:
            return []

        deviation = abs(self._angle_diff(gps.heading, road_bearing))
        if deviation > self._threshold:
            # Wrong-side confidence proportional to deviation
            conf = min(1.0, deviation / 180.0)
            return [(0, conf)]  # track_id 0 for GPS-based rules

        return []

    @staticmethod
    def _angle_diff(a: float, b: float) -> float:
        """Compute the signed shortest angle difference between two bearings."""
        diff = (a - b + 180) % 360 - 180
        return diff


class RuleEngine:
    """Orchestrates all violation rules.

    For each frame:
    1. Run all enabled rules
    2. Feed results through temporal consistency checker
    3. Aggregate confidence
    4. Emit ViolationCandidate if temporal threshold met
    5. Apply cooldown to prevent duplicate reports
    """

    def __init__(
        self,
        rules: Optional[list[ViolationRule]] = None,
        rule_configs: Optional[dict[str, dict]] = None,
        speed_gate_kmh: float = 5.0,
        max_reports_per_hour: int = 20,
    ):
        """
        Args:
            rules: List of ViolationRule instances.
            rule_configs: Per-rule configuration from violation_rules.yaml.
            speed_gate_kmh: Minimum GPS speed to process violations.
            max_reports_per_hour: Rate limit for violation reports.
        """
        self._rules = rules or [
            NoHelmetRule(),
            RedLightJumpRule(),
            WrongSideRule(),
        ]
        self._rule_configs = rule_configs or {}
        self._speed_gate_kmh = speed_gate_kmh
        self._max_reports_per_hour = max_reports_per_hour

        self._temporal = TemporalConsistencyChecker()
        self._confidence = ConfidenceAggregator()

        # Cooldown tracking: violation_type -> last report timestamp
        self._cooldowns: dict[str, float] = {}
        self._report_times: list[float] = []

    def process_frame(
        self,
        frame_data: FrameData,
        context: Optional[dict] = None,
    ) -> list[ViolationCandidate]:
        """Process a single frame through all rules.

        Args:
            frame_data: Current frame data with detections.
            context: Additional context (signal state, helmet results, etc.).

        Returns:
            List of violation candidates that passed temporal consistency.
        """
        ctx = context or {}
        violations = []

        # GPS speed gate: skip processing when stationary
        if frame_data.gps and frame_data.gps.speed_kmh < self._speed_gate_kmh:
            return []

        for rule in self._rules:
            vtype = rule.violation_type.value
            config = self._rule_configs.get(vtype, {})

            if not config.get("enabled", True):
                continue

            min_frames = config.get("min_consecutive_frames", 3)
            conf_threshold = config.get("confidence_threshold", 0.7)

            # Evaluate rule
            hits = rule.evaluate(frame_data, ctx)

            for track_id, raw_conf in hits:
                if raw_conf < conf_threshold:
                    continue

                # Temporal consistency check
                confirmed = self._temporal.update(
                    vtype, track_id, True, min_frames
                )

                if confirmed:
                    # Check cooldown and rate limit
                    if self._check_cooldown(vtype) and self._check_rate_limit():
                        count = self._temporal.get_count(vtype, track_id)
                        temporal_ratio = count / min_frames

                        agg_conf = self._confidence.compute(
                            detection_conf=raw_conf,
                            classification_conf=ctx.get("classification_conf", raw_conf),
                            temporal_ratio=temporal_ratio,
                        )

                        candidate = ViolationCandidate(
                            violation_type=rule.violation_type,
                            confidence=agg_conf,
                            gps=frame_data.gps,
                            timestamp=frame_data.timestamp,
                            consecutive_frame_count=count,
                        )
                        if frame_data.frame is not None:
                            candidate.best_frame = frame_data

                        violations.append(candidate)
                        self._record_report(vtype)

            # Reset temporal counters for tracks where condition was NOT met
            active_hits = {tid for tid, _ in hits}
            for det in frame_data.detections:
                if det.track_id is not None and det.track_id not in active_hits:
                    self._temporal.update(vtype, det.track_id, False, min_frames)

        return violations

    def _check_cooldown(self, violation_type: str, cooldown_seconds: int = 30) -> bool:
        """Check if enough time has passed since last report of this type."""
        config = self._rule_configs.get(violation_type, {})
        cooldown = config.get("cooldown_seconds", cooldown_seconds)
        last = self._cooldowns.get(violation_type, 0)
        return (time.monotonic() - last) >= cooldown

    def _check_rate_limit(self) -> bool:
        """Check hourly rate limit."""
        now = time.monotonic()
        # Remove entries older than 1 hour
        self._report_times = [t for t in self._report_times if now - t < 3600]
        return len(self._report_times) < self._max_reports_per_hour

    def _record_report(self, violation_type: str) -> None:
        """Record that a report was generated."""
        now = time.monotonic()
        self._cooldowns[violation_type] = now
        self._report_times.append(now)

    def reset(self) -> None:
        """Reset all state."""
        self._temporal.reset_all()
        self._cooldowns.clear()
        self._report_times.clear()
