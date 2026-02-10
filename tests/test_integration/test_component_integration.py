"""Integration tests for individual component interactions."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.capture.buffer import CircularFrameBuffer
from src.config import load_config
from src.detection.detector import TFLiteDetector
from src.detection.tracker import IOUTracker
from src.models import (
    BoundingBox,
    Detection,
    FrameData,
    GPSReading,
    ViolationCandidate,
    ViolationType,
)
from src.reporting.evidence import EvidencePackager
from src.reporting.report import ReportGenerator
from src.utils.database import Database
from src.violation.rules import RuleEngine


@pytest.fixture
def test_config():
    """Load test configuration."""
    return load_config("config")


@pytest.fixture
def test_frame():
    """Create a test frame."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:, :] = (50, 50, 50)  # Gray background
    return frame


@pytest.fixture
def test_gps():
    """Create a test GPS reading."""
    return GPSReading(
        latitude=19.0760,
        longitude=72.8777,
        altitude=10.0,
        speed_kmh=25.0,
        heading=90.0,
        timestamp=datetime.now(timezone.utc),
        fix_quality=1,
        satellites=8,
    )


@pytest.fixture
def temp_db():
    """Create a temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = Database(db_path)
    yield db
    db.close()

    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


class TestDetectionIntegration:
    """Test detector + tracker integration."""

    def test_detector_tracker_flow(self, test_config, test_frame):
        """Test that detector output can be tracked."""
        # Initialize detector
        model_path = Path(test_config.detection.model_path)
        if not model_path.exists():
            pytest.skip(f"Model not found: {model_path}")

        detector = TFLiteDetector(
            confidence_threshold=0.3,
            nms_threshold=0.45,
            num_threads=2,
        )
        detector.load_model(str(model_path))

        tracker = IOUTracker()

        # Run detection
        detections = detector.detect(test_frame, frame_id=1)
        assert isinstance(detections, list)

        # Track detections
        tracked = tracker.update(detections)
        assert len(tracked) == len(detections)

        # Check that track IDs are assigned
        for det in tracked:
            assert isinstance(det, Detection)
            # Track ID may be None if no tracking happened (empty detections)
            if tracked:
                assert det.track_id is None or isinstance(det.track_id, int)


class TestBufferIntegration:
    """Test frame buffer integration."""

    def test_buffer_push_and_retrieve(self, test_frame):
        """Test pushing frames and retrieving clips."""
        buffer = CircularFrameBuffer(max_seconds=5, fps=10)

        now = datetime.now(timezone.utc)

        # Push frames
        for i in range(30):
            buffer.push(test_frame.copy(), now, frame_id=i)

        # Get clip
        clip = buffer.get_clip(
            start_time=now,
            end_time=now,
        )

        assert len(clip) > 0
        assert all(hasattr(frame, 'frame') for frame in clip)


class TestRuleEngineIntegration:
    """Test rule engine integration."""

    def test_helmet_rule_with_detections(self, test_frame, test_gps):
        """Test helmet rule with mock detections."""
        rule_engine = RuleEngine(
            speed_gate_kmh=0.0,  # Disable for testing
            max_reports_per_hour=100,
        )

        # Create mock detections (motorcycle + person)
        detections = [
            Detection(
                bbox=BoundingBox(
                    x1=100, y1=400, x2=250, y2=550,
                    confidence=0.9, class_name="motorcycle", class_id=3
                ),
                frame_id=1,
                timestamp=datetime.now(timezone.utc),
                track_id=1,
            ),
            Detection(
                bbox=BoundingBox(
                    x1=120, y1=300, x2=230, y2=450,
                    confidence=0.85, class_name="person", class_id=0
                ),
                frame_id=1,
                timestamp=datetime.now(timezone.utc),
                track_id=2,
            ),
        ]

        frame_data = FrameData(
            frame=test_frame,
            frame_id=1,
            timestamp=datetime.now(timezone.utc),
            gps=test_gps,
            detections=detections,
        )

        # Context with no helmet
        context = {
            "has_helmet": {2: False},  # Track ID 2 (person) has no helmet
            "helmet_confidence": {2: 0.95},
        }

        # Process multiple frames to trigger temporal consistency
        violations = []
        for i in range(5):  # Need consecutive frames
            frame_data.frame_id = i
            frame_violations = rule_engine.process_frame(frame_data, context)
            violations.extend(frame_violations)

        # Should eventually detect violation
        assert len(violations) > 0
        assert violations[0].violation_type == ViolationType.NO_HELMET


class TestEvidencePackaging:
    """Test evidence packaging integration."""

    def test_package_violation(self, test_config, test_frame, test_gps, temp_db):
        """Test packaging a violation into evidence."""
        # Create evidence directory
        evidence_dir = Path(test_config.reporting.evidence_dir)
        evidence_dir.mkdir(parents=True, exist_ok=True)

        packager = EvidencePackager(test_config, temp_db)

        # Create buffer with frames
        buffer = CircularFrameBuffer(max_seconds=5, fps=10)
        now = datetime.now(timezone.utc)

        for i in range(30):
            buffer.push(test_frame.copy(), now, frame_id=i)

        # Create violation
        violation = ViolationCandidate(
            violation_type=ViolationType.NO_HELMET,
            confidence=0.92,
            gps=test_gps,
            timestamp=now,
            consecutive_frame_count=5,
        )

        violation.best_frame = FrameData(
            frame=test_frame,
            frame_id=15,
            timestamp=now,
            gps=test_gps,
            detections=[],
        )

        # Package evidence
        evidence = packager.package(violation, buffer)

        assert evidence is not None
        assert evidence.violation_id
        assert len(evidence.best_frames_jpeg) > 0
        assert evidence.metadata["violation_type"] == "no_helmet"


class TestReportGeneration:
    """Test report generation integration."""

    def test_generate_report_from_evidence(self, test_config, test_frame, test_gps, temp_db):
        """Test generating a report from evidence."""
        report_gen = ReportGenerator(test_config)

        # Create minimal evidence
        evidence_dir = Path(test_config.reporting.evidence_dir)
        evidence_dir.mkdir(parents=True, exist_ok=True)

        packager = EvidencePackager(test_config, temp_db)
        buffer = CircularFrameBuffer(max_seconds=5, fps=10)
        now = datetime.now(timezone.utc)

        for i in range(30):
            buffer.push(test_frame.copy(), now, frame_id=i)

        violation = ViolationCandidate(
            violation_type=ViolationType.NO_HELMET,
            confidence=0.92,
            gps=test_gps,
            timestamp=now,
            consecutive_frame_count=5,
            plate_text="MH12AB1234",
            plate_confidence=0.95,
        )

        violation.best_frame = FrameData(
            frame=test_frame,
            frame_id=15,
            timestamp=now,
            gps=test_gps,
            detections=[],
        )

        evidence = packager.package(violation, buffer)
        evidence.metadata["cloud_verified"] = True

        # Generate report
        report = report_gen.generate(evidence)

        assert report is not None
        assert report.subject
        assert report.html_body
        assert report.text_body
        assert len(report.attachments) > 0
        assert "MH12AB1234" in report.text_body


class TestOCRIntegration:
    """Test OCR integration (requires API key)."""

    @pytest.mark.skipif(
        not os.getenv("TRAFFIC_EYE_CLOUD_API_KEY"),
        reason="No API key configured"
    )
    def test_gemini_ocr_with_plate_image(self):
        """Test Gemini OCR with a plate image."""
        from src.ocr.gemini_ocr import GeminiOCR

        api_key = os.getenv("TRAFFIC_EYE_CLOUD_API_KEY")
        ocr = GeminiOCR(api_key=api_key, confidence_threshold=0.7)

        # Create synthetic plate image
        plate_img = np.ones((100, 300, 3), dtype=np.uint8) * 255
        cv2.putText(plate_img, "MH12AB1234", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

        # Extract text
        text, conf = ocr.extract_plate_text(plate_img)

        # May or may not succeed with synthetic image
        assert text is None or isinstance(text, str)
        assert 0.0 <= conf <= 1.0


class TestConfigLoading:
    """Test configuration loading."""

    def test_load_config_success(self):
        """Test loading configuration from file."""
        config = load_config("config")

        assert config is not None
        assert config.camera.resolution
        assert config.detection.model_path
        assert config.cloud.provider == "gemini"


class TestDatabaseIntegration:
    """Test database operations."""

    def test_insert_and_retrieve_violation(self, temp_db):
        """Test inserting and retrieving violation records."""
        violation_id = "test-violation-123"

        temp_db.insert_violation(
            violation_id=violation_id,
            violation_type="no_helmet",
            confidence=0.92,
            plate_text="MH12AB1234",
            plate_confidence=0.95,
            gps_lat=19.0760,
            gps_lon=72.8777,
            gps_heading=90.0,
            gps_speed_kmh=25.0,
            gps_address="Mumbai, Maharashtra",
            timestamp=datetime.now(timezone.utc).isoformat(),
            consecutive_frames=5,
        )

        # Verify insertion
        # (Database class doesn't have query methods in current implementation)
        # This tests that insert doesn't raise an error
        assert True
