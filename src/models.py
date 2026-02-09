"""Core data models shared across all modules."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import numpy as np


class ViolationType(Enum):
    NO_HELMET = "no_helmet"
    RED_LIGHT_JUMP = "red_light_jump"
    WRONG_SIDE = "wrong_side"


class SignalState(Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    UNKNOWN = "unknown"


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_name: str
    class_id: int = 0

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def iou(self, other: BoundingBox) -> float:
        """Compute Intersection over Union with another bounding box."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)

        inter_w = max(0.0, ix2 - ix1)
        inter_h = max(0.0, iy2 - iy1)
        inter_area = inter_w * inter_h

        union_area = self.area + other.area - inter_area
        if union_area <= 0:
            return 0.0
        return inter_area / union_area

    def to_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def to_xywh(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.width, self.height)


@dataclass
class Detection:
    bbox: BoundingBox
    frame_id: int
    timestamp: datetime
    track_id: Optional[int] = None


@dataclass
class GPSReading:
    latitude: float
    longitude: float
    altitude: float
    speed_kmh: float
    heading: float
    timestamp: datetime
    fix_quality: int = 0
    satellites: int = 0

    @property
    def has_fix(self) -> bool:
        return self.fix_quality > 0

    def google_maps_url(self) -> str:
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"


@dataclass
class FrameData:
    frame: np.ndarray  # HWC, BGR format
    frame_id: int
    timestamp: datetime
    gps: Optional[GPSReading] = None
    detections: list[Detection] = field(default_factory=list)

    @property
    def height(self) -> int:
        return self.frame.shape[0]

    @property
    def width(self) -> int:
        return self.frame.shape[1]


@dataclass
class ViolationCandidate:
    violation_type: ViolationType
    confidence: float
    frames: list[FrameData] = field(default_factory=list)
    best_frame: Optional[FrameData] = None
    plate_text: Optional[str] = None
    plate_confidence: float = 0.0
    gps: Optional[GPSReading] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_frame_count: int = 0


@dataclass
class EvidencePacket:
    violation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    violation: Optional[ViolationCandidate] = None
    best_frames_jpeg: list[bytes] = field(default_factory=list)
    video_clip_path: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    file_hashes: dict[str, str] = field(default_factory=dict)
