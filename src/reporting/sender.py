"""Email sender with queue processing and retry logic."""

from __future__ import annotations

import logging
import smtplib
import socket
import time
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Optional

from src.config import AppConfig
from src.models import EvidencePacket
from src.reporting.report import Report, ReportGenerator
from src.utils.database import Database

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends violation reports via SMTP/TLS with crash-safe queuing.

    Features:
    - Queue-based: reads pending emails from SQLite (WAL mode)
    - Retry with exponential backoff (max 5 attempts)
    - Rate limiting (max N per hour from config)
    - Offline-aware: gracefully handles network failures
    - Cleanup: removes sent evidence files to save space
    """

    def __init__(
        self,
        config: AppConfig,
        db: Database,
        report_generator: Optional[ReportGenerator] = None,
    ):
        self._config = config
        self._db = db
        self._email_cfg = config.reporting.email
        self._report_gen = report_generator or ReportGenerator(config)
        self._max_attempts = 5
        self._send_times: list[float] = []

    def send(self, report: Report) -> bool:
        """Send a single report via email with error handling.

        Args:
            report: The report to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._validate_config():
            return False

        msg = self._build_mime_message(report)

        try:
            with self._connect_smtp() as server:
                server.send_message(msg)
            logger.info(
                "Email sent: %s -> %s",
                report.subject, self._email_cfg.recipients
            )
            self._send_times.append(time.monotonic())
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error("SMTP auth failed: %s", e)
            return False
        except smtplib.SMTPException as e:
            logger.error("SMTP error: %s", e)
            return False
        except socket.gaierror as e:
            logger.error("Network unavailable: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error sending email: %s", e)
            return False

    def process_queue(self) -> int:
        """Process pending emails from SQLite queue with retry logic.

        Returns:
            Number of emails successfully sent.
        """
        if not self._validate_config():
            logger.warning("Email not configured, skipping queue")
            return 0

        pending = self._db.get_pending_emails(limit=20)
        sent_count = 0

        for entry in pending:
            queue_id = entry["id"]
            violation_id = entry["violation_id"]
            attempts = entry.get("attempts", 0)

            # Check max attempts
            if attempts >= self._max_attempts:
                self._db.update_email_status(
                    queue_id, "failed",
                    error_message="Max retry attempts exceeded"
                )
                logger.warning(
                    "Email queue %d failed after %d attempts",
                    queue_id, attempts
                )
                continue

            # Check rate limit
            if not self._check_rate_limit():
                logger.info("Rate limit reached, pausing queue")
                break

            # Exponential backoff for retries
            if attempts > 0:
                backoff = min(300, 2 ** attempts)
                logger.debug("Retry backoff: %ds", backoff)
                time.sleep(backoff)

            # Mark as processing
            self._db.update_email_status(queue_id, "processing")

            # Reconstruct report from stored evidence
            try:
                report = self._reconstruct_report(violation_id)
                if not report:
                    self._db.update_email_status(
                        queue_id, "failed",
                        error_message="Evidence not found"
                    )
                    continue

                # Attempt to send
                if self.send(report):
                    self._db.update_email_status(queue_id, "sent")
                    sent_count += 1

                    # Cleanup evidence files to save space
                    self._cleanup_evidence(violation_id)
                    logger.info("Email sent: queue_id=%d", queue_id)
                else:
                    # Network error - leave as pending for retry
                    self._db.update_email_status(
                        queue_id, "pending",
                        error_message="Send failed (network error)"
                    )
                    logger.warning("Email send failed, will retry")

            except Exception as e:
                logger.error("Queue processing error: %s", e)
                self._db.update_email_status(
                    queue_id, "pending",
                    error_message=f"Processing error: {e}"
                )

        return sent_count

    def _validate_config(self) -> bool:
        """Check if email is properly configured."""
        if not self._email_cfg.sender or not self._email_cfg.recipients:
            logger.warning("Email not configured (missing sender/recipients)")
            return False

        if not self._email_cfg.password:
            logger.warning(
                "Email password not set (env: %s)",
                self._email_cfg.password_env
            )
            return False

        return True

    def _check_rate_limit(self) -> bool:
        """Check if we're within the hourly rate limit."""
        now = time.monotonic()
        self._send_times = [t for t in self._send_times if now - t < 3600]
        max_per_hour = self._config.violations.max_reports_per_hour
        return len(self._send_times) < max_per_hour

    def _connect_smtp(self) -> smtplib.SMTP:
        """Create and authenticate SMTP connection with TLS."""
        server = smtplib.SMTP(
            self._email_cfg.smtp_host,
            self._email_cfg.smtp_port,
            timeout=30
        )
        server.ehlo()
        if self._email_cfg.use_tls:
            server.starttls()
            server.ehlo()
        password = self._email_cfg.password
        if password:
            server.login(self._email_cfg.sender, password)
        return server

    def _build_mime_message(self, report: Report) -> MIMEMultipart:
        """Build a MIME email message with attachments."""
        msg = MIMEMultipart("mixed")
        msg["Subject"] = report.subject
        msg["From"] = self._email_cfg.sender
        msg["To"] = ", ".join(self._email_cfg.recipients)

        # HTML body
        html_part = MIMEMultipart("alternative")
        html_part.attach(MIMEText(report.text_body, "plain"))
        html_part.attach(MIMEText(report.html_body, "html"))
        msg.attach(html_part)

        # Attachments
        for filename, data in report.attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={filename}"
            )
            msg.attach(part)

        return msg

    def _reconstruct_report(self, violation_id: str) -> Optional[Report]:
        """Reconstruct report from stored evidence."""
        violation = self._db.get_violation(violation_id)
        if not violation:
            logger.error("Violation not found: %s", violation_id)
            return None

        # Get evidence files
        evidence_files = self._db.get_evidence_files(violation_id)
        if not evidence_files:
            logger.error("No evidence files for: %s", violation_id)
            return None

        # Load frame JPEGs
        best_frames_jpeg = []
        for ef in sorted(evidence_files, key=lambda x: x["file_path"]):
            if ef["file_type"] == "frame":
                try:
                    fpath = Path(ef["file_path"])
                    if fpath.exists():
                        best_frames_jpeg.append(fpath.read_bytes())
                except Exception as e:
                    logger.warning("Failed to read %s: %s", fpath, e)

        # Create minimal evidence packet for report generation
        from src.models import (
            ViolationCandidate, ViolationType, GPSReading
        )
        from datetime import datetime

        vtype = ViolationType(violation["type"])
        timestamp = datetime.fromisoformat(violation["timestamp"])

        gps = None
        if violation["gps_lat"] and violation["gps_lon"]:
            gps = GPSReading(
                latitude=violation["gps_lat"],
                longitude=violation["gps_lon"],
                altitude=0.0,
                speed_kmh=violation["gps_speed_kmh"] or 0.0,
                heading=violation["gps_heading"] or 0.0,
                timestamp=timestamp,
            )

        candidate = ViolationCandidate(
            violation_type=vtype,
            confidence=violation["confidence"],
            plate_text=violation.get("plate_text"),
            plate_confidence=violation.get("plate_confidence", 0.0),
            gps=gps,
            timestamp=timestamp,
            consecutive_frame_count=violation.get("consecutive_frames", 0),
        )

        evidence = EvidencePacket(
            violation_id=violation_id,
            violation=candidate,
            best_frames_jpeg=best_frames_jpeg,
            metadata={"reconstructed": True},
        )

        return self._report_gen.generate(evidence)

    def _cleanup_evidence(self, violation_id: str) -> None:
        """Delete evidence files after successful send."""
        evidence_files = self._db.get_evidence_files(violation_id)
        for ef in evidence_files:
            try:
                fpath = Path(ef["file_path"])
                if fpath.exists():
                    fpath.unlink()
                    logger.debug("Cleaned up: %s", fpath)
            except Exception as e:
                logger.warning("Cleanup failed for %s: %s", fpath, e)
