"""Tests for core data models."""

from datetime import datetime, timezone

import numpy as np

from src.models import (
    BoundingBox,
    Detection,
    EvidencePacket,
    FrameData,
    GPSReading,
    SignalState,
    ViolationCandidate,
    ViolationType,
)


class TestBoundingBox:
    def test_properties(self):
        bb = BoundingBox(x1=10, y1=20, x2=110, y2=120, confidence=0.9, class_name="car")
        assert bb.width == 100
        assert bb.height == 100
        assert bb.area == 10000
        assert bb.center == (60.0, 70.0)

    def test_iou_identical(self):
        bb = BoundingBox(x1=0, y1=0, x2=100, y2=100, confidence=0.9, class_name="car")
        assert bb.iou(bb) == 1.0

    def test_iou_no_overlap(self):
        bb1 = BoundingBox(x1=0, y1=0, x2=50, y2=50, confidence=0.9, class_name="car")
        bb2 = BoundingBox(x1=100, y1=100, x2=150, y2=150, confidence=0.9, class_name="car")
        assert bb1.iou(bb2) == 0.0

    def test_iou_partial_overlap(self):
        bb1 = BoundingBox(x1=0, y1=0, x2=100, y2=100, confidence=0.9, class_name="car")
        bb2 = BoundingBox(x1=50, y1=50, x2=150, y2=150, confidence=0.9, class_name="car")
        # Intersection: 50x50=2500, Union: 10000+10000-2500=17500
        expected = 2500 / 17500
        assert abs(bb1.iou(bb2) - expected) < 0.001

    def test_iou_zero_area(self):
        bb1 = BoundingBox(x1=0, y1=0, x2=0, y2=0, confidence=0.9, class_name="car")
        bb2 = BoundingBox(x1=10, y1=10, x2=20, y2=20, confidence=0.9, class_name="car")
        assert bb1.iou(bb2) == 0.0

    def test_to_xyxy(self):
        bb = BoundingBox(x1=10, y1=20, x2=30, y2=40, confidence=0.5, class_name="person")
        assert bb.to_xyxy() == (10, 20, 30, 40)

    def test_to_xywh(self):
        bb = BoundingBox(x1=10, y1=20, x2=30, y2=40, confidence=0.5, class_name="person")
        assert bb.to_xywh() == (10, 20, 20, 20)


class TestGPSReading:
    def test_has_fix(self):
        gps = GPSReading(
            latitude=12.97, longitude=77.59, altitude=920,
            speed_kmh=30, heading=90,
            timestamp=datetime.now(timezone.utc),
            fix_quality=1, satellites=8,
        )
        assert gps.has_fix is True

    def test_no_fix(self):
        gps = GPSReading(
            latitude=0, longitude=0, altitude=0,
            speed_kmh=0, heading=0,
            timestamp=datetime.now(timezone.utc),
            fix_quality=0, satellites=0,
        )
        assert gps.has_fix is False

    def test_google_maps_url(self):
        gps = GPSReading(
            latitude=12.9716, longitude=77.5946, altitude=920,
            speed_kmh=30, heading=90,
            timestamp=datetime.now(timezone.utc),
        )
        assert "12.9716" in gps.google_maps_url()
        assert "77.5946" in gps.google_maps_url()


class TestFrameData:
    def test_dimensions(self, sample_frame):
        fd = FrameData(
            frame=sample_frame,
            frame_id=0,
            timestamp=datetime.now(timezone.utc),
        )
        assert fd.height == 480
        assert fd.width == 640


class TestViolationCandidate:
    def test_defaults(self):
        vc = ViolationCandidate(
            violation_type=ViolationType.NO_HELMET,
            confidence=0.9,
        )
        assert vc.plate_text is None
        assert vc.consecutive_frame_count == 0
        assert vc.timestamp is not None


class TestEvidencePacket:
    def test_uuid_generated(self):
        ep1 = EvidencePacket()
        ep2 = EvidencePacket()
        assert ep1.violation_id != ep2.violation_id
        assert len(ep1.violation_id) == 36  # UUID format
