"""Tests for email sender with queue processing and retry logic."""

import socket
import smtplib
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import AppConfig, EmailConfig, ReportingConfig, ViolationsConfig
from src.reporting.report import Report, ReportGenerator
from src.reporting.sender import EmailSender
from src.utils.database import Database


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def mock_config():
    """Create a test config with email settings."""
    email_config = EmailConfig(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        use_tls=True,
        sender="test@example.com",
        password_env="TEST_EMAIL_PASSWORD",
        recipients=("recipient@example.com",),
    )

    violations_config = ViolationsConfig(
        max_reports_per_hour=20,
    )

    return AppConfig(
        reporting=ReportingConfig(email=email_config),
        violations=violations_config,
    )


@pytest.fixture
def mock_db(temp_dir):
    """Create a test database."""
    db_path = str(Path(temp_dir) / "test.db")
    return Database(db_path)


@pytest.fixture
def sample_report():
    """Create a sample report."""
    return Report(
        subject="Test Violation Report",
        html_body="<html><body>Test</body></html>",
        text_body="Test violation",
        attachments=[("evidence_00.jpg", b"fake jpeg data")],
        violation_id="test-123",
    )


class TestEmailSender:
    """Test email sending functionality."""

    @patch.dict("os.environ", {"TEST_EMAIL_PASSWORD": "test_password"})
    @patch("smtplib.SMTP")
    def test_send_success(self, mock_smtp_class, mock_config, mock_db, sample_report):
        """Test successful email send."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        sender = EmailSender(mock_config, mock_db)
        result = sender.send(sample_report)

        assert result is True
        mock_server.send_message.assert_called_once()

    def test_send_without_config(self, mock_db, sample_report):
        """Test that send fails gracefully without config."""
        config = AppConfig(
            reporting=ReportingConfig(
                email=EmailConfig(sender="", recipients=())
            )
        )

        sender = EmailSender(config, mock_db)
        result = sender.send(sample_report)

        assert result is False

    @patch.dict("os.environ", {}, clear=True)
    def test_send_without_password(self, mock_config, mock_db, sample_report):
        """Test that send fails without password."""
        sender = EmailSender(mock_config, mock_db)
        result = sender.send(sample_report)

        assert result is False

    @patch.dict("os.environ", {"TEST_EMAIL_PASSWORD": "test_password"})
    @patch("smtplib.SMTP")
    def test_send_smtp_auth_error(
        self, mock_smtp_class, mock_config, mock_db, sample_report
    ):
        """Test handling of SMTP authentication error."""
        mock_server = MagicMock()
        # Set side effect on the instance returned by context manager or constructor
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, "Bad auth")
        
        # Ensure mock_smtp_class returns this mock
        mock_smtp_class.return_value = mock_server
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        sender = EmailSender(mock_config, mock_db)
        result = sender.send(sample_report)

        assert result is False

    @patch.dict("os.environ", {"TEST_EMAIL_PASSWORD": "test_password"})
    @patch("smtplib.SMTP")
    def test_send_network_error(
        self, mock_smtp_class, mock_config, mock_db, sample_report
    ):
        """Test handling of network error."""
        mock_smtp_class.side_effect = socket.gaierror("Network unavailable")

        sender = EmailSender(mock_config, mock_db)
        result = sender.send(sample_report)

        assert result is False

    @patch.dict("os.environ", {"TEST_EMAIL_PASSWORD": "test_password"})
    @patch("smtplib.SMTP")
    def test_process_queue_success(
        self, mock_smtp_class, mock_config, mock_db, temp_dir
    ):
        """Test successful queue processing."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        # Create a violation and queue entry
        violation_id = "test-violation-1"
        mock_db.insert_violation(
            violation_id=violation_id,
            violation_type="no_helmet",
            confidence=0.95,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Create evidence files
        evidence_dir = Path(temp_dir) / violation_id
        evidence_dir.mkdir(parents=True)

        frame_path = evidence_dir / "frame_00.jpg"
        frame_path.write_bytes(b"\xff\xd8\xff\xe0")  # JPEG magic

        mock_db.insert_evidence_file(
            violation_id=violation_id,
            file_path=str(frame_path),
            file_type="frame",
            file_size=4,
        )

        # Enqueue email
        mock_db.enqueue_email(violation_id)

        # Process queue
        report_gen = ReportGenerator(mock_config, template_dir=str(Path(temp_dir)))
        sender = EmailSender(mock_config, mock_db, report_gen)
        sent_count = sender.process_queue()

        assert sent_count == 1

        # Verify status updated
        queue_entry = mock_db.get_pending_emails(limit=10)
        assert len(queue_entry) == 0  # Should be sent, not pending

    def test_process_queue_retry_logic(self, mock_config, mock_db):
        """Test exponential backoff retry logic."""
        # Create violation
        violation_id = "test-violation-retry"
        mock_db.insert_violation(
            violation_id=violation_id,
            violation_type="no_helmet",
            confidence=0.95,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Enqueue email
        queue_id = mock_db.enqueue_email(violation_id)

        # Mark as failed once to trigger retry
        mock_db.update_email_status(queue_id, "pending")

        sender = EmailSender(mock_config, mock_db)

        with patch("time.sleep") as mock_sleep:
            with patch.object(sender, "send", return_value=False):
                sender.process_queue()

                # Should have tried backoff (but email send failed)
                # No backoff on first attempt
                mock_sleep.assert_not_called()

    @patch.dict("os.environ", {"TEST_EMAIL_PASSWORD": "test_password"})
    def test_process_queue_max_attempts(self, mock_config, mock_db):
        """Test that max retry attempts are respected."""
        violation_id = "test-violation-max"
        mock_db.insert_violation(
            violation_id=violation_id,
            violation_type="no_helmet",
            confidence=0.95,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        queue_id = mock_db.enqueue_email(violation_id)

        # Simulate max attempts reached directly
        mock_db._conn.execute(
            "UPDATE email_queue SET attempts = ?, status = 'pending' WHERE id = ?",
            (5, queue_id)
        )
        mock_db._conn.commit()

        sender = EmailSender(mock_config, mock_db)
        sent_count = sender.process_queue()

        assert sent_count == 0

        # Should be marked as failed
        queue_entry = mock_db._conn.execute(
            "SELECT status, attempts FROM email_queue WHERE id = ?", (queue_id,)
        ).fetchone()
        assert queue_entry["status"] == "failed"

    def test_rate_limiting(self, mock_config, mock_db):
        """Test that rate limiting works."""
        sender = EmailSender(mock_config, mock_db)

        # Simulate 20 sends (the limit)
        sender._send_times = [time.monotonic()] * 20

        assert sender._check_rate_limit() is False

        # After an hour, should allow more
        sender._send_times = [time.monotonic() - 3601] * 20
        assert sender._check_rate_limit() is True

    @patch.dict("os.environ", {"TEST_EMAIL_PASSWORD": "test_password"})
    @patch("smtplib.SMTP")
    def test_connect_smtp_with_tls(self, mock_smtp_class, mock_config, mock_db):
        """Test SMTP connection with TLS."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        sender = EmailSender(mock_config, mock_db)
        with sender._connect_smtp():
            pass

        mock_server.ehlo.assert_called()
        mock_server.starttls.assert_called()
        mock_server.login.assert_called_with("test@example.com", "test_password")

    def test_build_mime_message(self, mock_config, mock_db, sample_report):
        """Test MIME message construction."""
        sender = EmailSender(mock_config, mock_db)
        msg = sender._build_mime_message(sample_report)

        assert msg["Subject"] == "Test Violation Report"
        assert msg["From"] == "test@example.com"
        assert msg["To"] == "recipient@example.com"

        # Should have attachments
        parts = list(msg.walk())
        assert len(parts) > 1

    @patch.dict("os.environ", {"TEST_EMAIL_PASSWORD": "test_password"})
    def test_reconstruct_report(self, mock_config, mock_db, temp_dir):
        """Test report reconstruction from database."""
        violation_id = "test-reconstruct"
        mock_db.insert_violation(
            violation_id=violation_id,
            violation_type="no_helmet",
            confidence=0.95,
            plate_text="KA01AB1234",
            plate_confidence=0.88,
            gps_lat=12.9716,
            gps_lon=77.5946,
            gps_speed_kmh=35.0,
            gps_heading=90.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Create evidence file
        evidence_dir = Path(temp_dir) / violation_id
        evidence_dir.mkdir(parents=True)
        frame_path = evidence_dir / "frame_00.jpg"
        frame_path.write_bytes(b"\xff\xd8\xff\xe0")

        mock_db.insert_evidence_file(
            violation_id=violation_id,
            file_path=str(frame_path),
            file_type="frame",
            file_size=4,
        )

        report_gen = ReportGenerator(mock_config)
        sender = EmailSender(mock_config, mock_db, report_gen)
        report = sender._reconstruct_report(violation_id)

        assert report is not None
        assert "no_helmet" in report.subject.lower() or "helmet" in report.subject.lower()
        assert len(report.attachments) >= 1

    def test_cleanup_evidence(self, mock_config, mock_db, temp_dir):
        """Test evidence cleanup after successful send."""
        violation_id = "test-cleanup"
        mock_db.insert_violation(
            violation_id=violation_id,
            violation_type="no_helmet",
            confidence=0.95,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        evidence_dir = Path(temp_dir) / violation_id
        evidence_dir.mkdir(parents=True)

        frame_path = evidence_dir / "frame_00.jpg"
        frame_path.write_bytes(b"test data")

        mock_db.insert_evidence_file(
            violation_id=violation_id,
            file_path=str(frame_path),
            file_type="frame",
            file_size=9,
        )

        sender = EmailSender(mock_config, mock_db)
        sender._cleanup_evidence(violation_id)

        # File should be deleted
        assert not frame_path.exists()

    @patch.dict("os.environ", {"TEST_EMAIL_PASSWORD": "test_password"})
    def test_process_queue_without_evidence(self, mock_config, mock_db):
        """Test queue processing when evidence is missing."""
        violation_id = "test-no-evidence"
        mock_db.insert_violation(
            violation_id=violation_id,
            violation_type="no_helmet",
            confidence=0.95,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        queue_id = mock_db.enqueue_email(violation_id)

        # Verify pending count before processing
        pending = mock_db.get_pending_emails()
        assert len(pending) == 1
        
        sender = EmailSender(mock_config, mock_db)
        sent_count = sender.process_queue()

        assert sent_count == 0

        # Should be marked as failed
        queue_entry = mock_db._conn.execute(
            "SELECT status, error_message FROM email_queue WHERE id = ?",
            (queue_id,)
        ).fetchone()
        assert queue_entry["status"] == "failed"
        assert "Evidence not found" in queue_entry["error_message"]
