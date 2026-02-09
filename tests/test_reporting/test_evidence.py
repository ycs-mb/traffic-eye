"""Tests for evidence packaging."""

import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import cv2
import numpy as np
import pytest

from src.capture.buffer import BufferedFrame, CircularFrameBuffer
from src.config import AppConfig, ReportingConfig
from src.models import (
    BoundingBox,
    Detection,
    FrameData,
    GPSReading,
    ViolationCandidate,
    ViolationType,
)
from src.reporting.evidence import EvidencePackager
from src.utils.database import Database


@pytest.fixture
def temp_dir():
    """Create a temporary directory for evidence."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def mock_config(temp_dir):
    """Create a test config."""
    config = AppConfig()
    # Modify reporting config
    config = AppConfig(
        reporting=ReportingConfig(
            evidence_dir=str(Path(temp_dir) / "evidence"),
            best_frames_count=3,
            clip_before_seconds=2,
            clip_after_seconds=3,
        )
    )
    return config


@pytest.fixture
def mock_db(temp_dir):
    """Create a test database."""
    db_path = str(Path(temp_dir) / "test.db")
    return Database(db_path)


@pytest.fixture
def sample_frames():
    """Create sample frames for testing."""
    frames = []
    base_time = datetime.now(timezone.utc)

    for i in range(10):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        # Add some visual variation
        cv2.putText(
            frame, f"Frame {i}", (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
        )
        frames.append(
            BufferedFrame(
                frame=frame,
                frame_id=i,
                timestamp=base_time + timedelta(seconds=i * 0.125),
            )
        )
    return frames


@pytest.fixture
def sample_violation():
    """Create a sample violation candidate."""
    now = datetime.now(timezone.utc)

    bbox = BoundingBox(
        x1=100, y1=100, x2=200, y2=200,
        confidence=0.95, class_name="person", class_id=0
    )

    detection = Detection(
        bbox=bbox, frame_id=5, timestamp=now
    )

    frame_data = FrameData(
        frame=np.zeros((720, 1280, 3), dtype=np.uint8),
        frame_id=5,
        timestamp=now,
        detections=[detection],
    )

    gps = GPSReading(
        latitude=12.9716,
        longitude=77.5946,
        altitude=920.0,
        speed_kmh=35.0,
        heading=90.0,
        timestamp=now,
        fix_quality=1,
    )

    return ViolationCandidate(
        violation_type=ViolationType.NO_HELMET,
        confidence=0.95,
        frames=[frame_data],
        best_frame=frame_data,
        plate_text="KA01AB1234",
        plate_confidence=0.88,
        gps=gps,
        timestamp=now,
        consecutive_frame_count=5,
    )


class TestEvidencePackager:
    """Test evidence packaging functionality."""

    def test_package_creates_evidence_directory(
        self, mock_config, mock_db, sample_violation, sample_frames
    ):
        """Test that evidence directory is created."""
        packager = EvidencePackager(mock_config, mock_db)
        buffer = CircularFrameBuffer(10.0, 8.0)

        for bf in sample_frames:
            buffer.push(bf.frame, bf.timestamp, bf.frame_id)

        packet = packager.package(sample_violation, buffer)

        evidence_dir = Path(mock_config.reporting.evidence_dir) / packet.violation_id
        assert evidence_dir.exists()

    def test_package_extracts_best_frames(
        self, mock_config, mock_db, sample_violation, sample_frames
    ):
        """Test that best frames are extracted correctly."""
        packager = EvidencePackager(mock_config, mock_db)
        buffer = CircularFrameBuffer(10.0, 8.0)

        for bf in sample_frames:
            buffer.push(bf.frame, bf.timestamp, bf.frame_id)

        packet = packager.package(sample_violation, buffer)

        # Should have 3 best frames
        assert len(packet.best_frames_jpeg) == 3

        # Each should be valid JPEG data
        for jpeg_data in packet.best_frames_jpeg:
            assert len(jpeg_data) > 0
            assert jpeg_data[:2] == b"\xff\xd8"  # JPEG magic bytes

    def test_package_includes_metadata(
        self, mock_config, mock_db, sample_violation, sample_frames
    ):
        """Test that metadata is properly included."""
        packager = EvidencePackager(mock_config, mock_db)
        buffer = CircularFrameBuffer(10.0, 8.0)

        for bf in sample_frames:
            buffer.push(bf.frame, bf.timestamp, bf.frame_id)

        packet = packager.package(sample_violation, buffer)

        assert packet.metadata["violation_type"] == "no_helmet"
        assert packet.metadata["confidence"] == 0.95
        assert packet.metadata["plate_text"] == "KA01AB1234"
        assert "gps" in packet.metadata
        assert packet.metadata["gps"]["lat"] == 12.9716
        assert packet.metadata["gps"]["lon"] == 77.5946

    def test_package_computes_file_hashes(
        self, mock_config, mock_db, sample_violation, sample_frames
    ):
        """Test that file hashes are computed."""
        packager = EvidencePackager(mock_config, mock_db)
        buffer = CircularFrameBuffer(10.0, 8.0)

        for bf in sample_frames:
            buffer.push(bf.frame, bf.timestamp, bf.frame_id)

        packet = packager.package(sample_violation, buffer)

        # Should have hashes for all frames
        assert len(packet.file_hashes) >= 3

        # Hashes should be SHA256 (64 hex chars)
        for file_hash in packet.file_hashes.values():
            assert len(file_hash) == 64
            assert all(c in "0123456789abcdef" for c in file_hash)

    def test_package_inserts_db_records(
        self, mock_config, mock_db, sample_violation, sample_frames
    ):
        """Test that database records are created."""
        packager = EvidencePackager(mock_config, mock_db)
        buffer = CircularFrameBuffer(10.0, 8.0)

        for bf in sample_frames:
            buffer.push(bf.frame, bf.timestamp, bf.frame_id)

        packet = packager.package(sample_violation, buffer)

        # Check violation record
        violation = mock_db.get_violation(packet.violation_id)
        assert violation is not None
        assert violation["type"] == "no_helmet"
        assert violation["confidence"] == 0.95

        # Check evidence files
        evidence_files = mock_db.get_evidence_files(packet.violation_id)
        assert len(evidence_files) >= 3

    def test_select_best_frames_by_confidence(
        self, mock_config, mock_db, sample_violation, sample_frames
    ):
        """Test that best frames are selected by confidence."""
        packager = EvidencePackager(mock_config, mock_db)

        # Create violation with frames that have different confidences
        frames_data = []
        for i, bf in enumerate(sample_frames[:5]):
            conf = 0.5 + (i * 0.1)  # Increasing confidence
            bbox = BoundingBox(
                x1=100, y1=100, x2=200, y2=200,
                confidence=conf, class_name="person", class_id=0
            )
            detection = Detection(bbox=bbox, frame_id=bf.frame_id, timestamp=bf.timestamp)
            fd = FrameData(
                frame=bf.frame,
                frame_id=bf.frame_id,
                timestamp=bf.timestamp,
                detections=[detection],
            )
            frames_data.append(fd)

        violation = ViolationCandidate(
            violation_type=ViolationType.NO_HELMET,
            confidence=0.95,
            frames=frames_data,
            timestamp=datetime.now(timezone.utc),
        )

        best = packager._select_best_frames(violation, sample_frames[:5], 3)

        # Should return 3 frames
        assert len(best) == 3

        # Should be the highest confidence frames (frame_ids 4, 3, 2)
        best_ids = sorted([bf.frame_id for bf in best], reverse=True)
        assert best_ids == [4, 3, 2]

    @patch("subprocess.run")
    def test_video_encoding_fallback(
        self, mock_run, mock_config, mock_db, sample_violation, sample_frames
    ):
        """Test that video encoding falls back to software encoding."""
        # Hardware encoding fails
        mock_run.side_effect = [
            Mock(returncode=1),  # HW encoding fails
            Mock(returncode=0),  # SW encoding succeeds
        ]

        packager = EvidencePackager(mock_config, mock_db)
        buffer = CircularFrameBuffer(10.0, 8.0)

        for bf in sample_frames:
            buffer.push(bf.frame, bf.timestamp, bf.frame_id)

        packet = packager.package(sample_violation, buffer)

        # Should have tried both methods
        assert mock_run.call_count == 2

        # First call should be hardware
        hw_call = mock_run.call_args_list[0]
        assert "h264_v4l2m2m" in " ".join(hw_call[0][0])

        # Second call should be software
        sw_call = mock_run.call_args_list[1]
        assert "libx264" in " ".join(sw_call[0][0])

    def test_package_handles_empty_buffer(
        self, mock_config, mock_db, sample_violation
    ):
        """Test graceful handling of empty buffer."""
        packager = EvidencePackager(mock_config, mock_db)
        buffer = CircularFrameBuffer(10.0, 8.0)

        packet = packager.package(sample_violation, buffer)

        # Should still create packet with no frames
        assert packet.violation_id
        assert len(packet.best_frames_jpeg) == 0

    def test_package_handles_missing_gps(
        self, mock_config, mock_db, sample_frames
    ):
        """Test handling of violation without GPS data."""
        violation = ViolationCandidate(
            violation_type=ViolationType.NO_HELMET,
            confidence=0.95,
            gps=None,
            timestamp=datetime.now(timezone.utc),
        )

        packager = EvidencePackager(mock_config, mock_db)
        buffer = CircularFrameBuffer(10.0, 8.0)

        for bf in sample_frames:
            buffer.push(bf.frame, bf.timestamp, bf.frame_id)

        packet = packager.package(violation, buffer)

        # Should not have GPS in metadata
        assert "gps" not in packet.metadata

    def test_annotate_frame_draws_bboxes(
        self, mock_config, mock_db, sample_violation
    ):
        """Test that annotation draws bounding boxes."""
        packager = EvidencePackager(mock_config, mock_db)

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        annotated = packager._annotate_frame(frame.copy(), sample_violation)

        # Annotated frame should be different from original
        assert not np.array_equal(frame, annotated)

    def test_compute_hash_consistency(self, mock_config, mock_db):
        """Test that hash computation is consistent."""
        packager = EvidencePackager(mock_config, mock_db)

        data = b"test data"
        hash1 = packager._compute_hash(data)
        hash2 = packager._compute_hash(data)

        assert hash1 == hash2
        assert len(hash1) == 64
