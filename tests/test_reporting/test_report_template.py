"""Tests for email template rendering."""

from datetime import datetime, timezone

import pytest

from src.config import AppConfig
from src.models import (
    EvidencePacket,
    GPSReading,
    ViolationCandidate,
    ViolationType,
)
from src.reporting.report import ReportGenerator


@pytest.fixture
def sample_violation():
    """Create a sample violation candidate."""
    now = datetime.now(timezone.utc)

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
        plate_text="KA01AB1234",
        plate_confidence=0.88,
        gps=gps,
        timestamp=now,
        consecutive_frame_count=5,
    )


@pytest.fixture
def sample_evidence(sample_violation):
    """Create a sample evidence packet."""
    return EvidencePacket(
        violation_id="test-12345678",
        violation=sample_violation,
        best_frames_jpeg=[b"\xff\xd8\xff\xe0" * 100],  # Fake JPEG
        metadata={
            "violation_type": "no_helmet",
            "confidence": 0.95,
            "cloud_verified": True,
        },
    )


class TestReportTemplate:
    """Test email template rendering."""

    def test_generate_report(self, sample_evidence):
        """Test basic report generation."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        assert report.subject
        assert "no_helmet" in report.subject.lower() or "helmet" in report.subject.lower()
        assert report.html_body
        assert report.text_body
        assert len(report.attachments) >= 1

    def test_html_body_contains_violation_details(self, sample_evidence):
        """Test that HTML body contains violation details."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        # Check HTML contains key information
        html = report.html_body.lower()
        assert "test-12345678" in html or "test-1234567" in html  # Violation ID
        assert "helmet" in html  # Violation type
        assert "ka01ab1234" in html  # Plate text
        assert "12.9716" in html or "12.97" in html  # GPS lat
        assert "77.5946" in html or "77.59" in html  # GPS lon

    def test_text_body_contains_violation_details(self, sample_evidence):
        """Test that text body contains violation details."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        # Check text contains key information
        text = report.text_body.lower()
        assert "test-12345678" in text or "test-1234567" in text
        assert "helmet" in text
        assert "ka01ab1234" in text

    def test_gps_coordinates_formatted(self, sample_evidence):
        """Test that GPS coordinates are properly formatted."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        html = report.html_body
        # Should contain Google Maps link
        assert "maps.google.com" in html or "google.com/maps" in html
        assert "12.9716" in html
        assert "77.5946" in html

    def test_confidence_score_displayed(self, sample_evidence):
        """Test that confidence scores are displayed."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        html = report.html_body
        # Should contain confidence percentage
        assert "95" in html  # 0.95 * 100 = 95%
        assert "88" in html  # 0.88 * 100 = 88%

    def test_plate_text_displayed(self, sample_evidence):
        """Test that plate text is displayed."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        assert "KA01AB1234" in report.html_body
        assert "KA01AB1234" in report.text_body

    def test_cloud_verification_badge(self, sample_evidence):
        """Test that cloud verification is shown when present."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        # Should mention cloud verification
        html = report.html_body.lower()
        assert "verif" in html

    def test_violation_without_gps(self, sample_evidence):
        """Test report generation without GPS data."""
        sample_evidence.violation.gps = None

        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        # Should still generate report
        assert report.html_body
        assert report.text_body

        # Should mention GPS unavailable
        text = report.text_body.lower()
        assert "unavailable" in text or "no gps" in text.replace(" ", "")

    def test_violation_without_plate(self, sample_evidence):
        """Test report generation without plate data."""
        sample_evidence.violation.plate_text = None
        sample_evidence.violation.plate_confidence = 0.0

        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        # Should still generate report
        assert report.html_body
        assert report.text_body

    def test_attachment_included(self, sample_evidence):
        """Test that evidence frames are included as attachments."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        assert len(report.attachments) >= 1

        # Check attachment format
        filename, data = report.attachments[0]
        assert filename.endswith(".jpg")
        assert len(data) > 0

    def test_disclaimer_included(self, sample_evidence):
        """Test that disclaimer is included in report."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        # Disclaimer should be in both HTML and text
        assert "disclaimer" in report.html_body.lower()
        assert "disclaimer" in report.text_body.lower()

    def test_timestamp_in_ist(self, sample_evidence):
        """Test that timestamp is displayed in IST."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        # Should mention IST timezone
        assert "IST" in report.html_body
        assert "IST" in report.text_body

    def test_subject_line_format(self, sample_evidence):
        """Test subject line format."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        report = generator.generate(sample_evidence)

        # Subject should be descriptive
        subject = report.subject
        assert len(subject) > 10
        assert len(subject) < 100
        # Should contain violation ID prefix
        assert "test-1234" in subject.lower()

    def test_multiple_violations_types(self):
        """Test rendering different violation types."""
        config = AppConfig()
        generator = ReportGenerator(config, template_dir="config")

        violation_types = [
            ViolationType.NO_HELMET,
            ViolationType.RED_LIGHT_JUMP,
            ViolationType.WRONG_SIDE,
        ]

        for vtype in violation_types:
            violation = ViolationCandidate(
                violation_type=vtype,
                confidence=0.95,
                timestamp=datetime.now(timezone.utc),
            )

            evidence = EvidencePacket(
                violation_id=f"test-{vtype.value}",
                violation=violation,
                best_frames_jpeg=[b"\xff\xd8\xff\xe0" * 100],
            )

            report = generator.generate(evidence)

            # Should generate valid report for each type
            assert report.html_body
            assert report.text_body
            assert vtype.value in report.subject.lower()
