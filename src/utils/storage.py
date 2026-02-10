"""Disk storage management and cleanup."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import AppConfig
from src.utils.database import Database

logger = logging.getLogger(__name__)


class StorageManager:
    """Monitors and manages disk usage.

    Policies:
    - If disk usage > threshold: delete oldest non-violation footage
    - Never delete pending violation evidence
    - Delete evidence older than retention_days
    - Log all storage operations
    """

    def __init__(self, config: AppConfig, db: Database):
        self._config = config
        self._db = db
        self._evidence_dir = Path(config.reporting.evidence_dir)

    def get_usage_percent(self) -> float:
        """Get current disk usage percentage for the evidence partition."""
        try:
            usage = shutil.disk_usage(str(self._evidence_dir))
            return (usage.used / usage.total) * 100
        except OSError as e:
            logger.error("Failed to get disk usage: %s", e)
            return 0.0

    def get_evidence_size_bytes(self) -> int:
        """Get total size of the evidence directory."""
        total = 0
        try:
            for f in self._evidence_dir.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        except OSError as e:
            logger.error("Failed to calculate evidence size: %s", e)
        return total

    def check_and_cleanup(self) -> int:
        """Check disk usage and clean up if needed.

        Returns:
            Total bytes freed.
        """
        bytes_freed = 0

        # Always run retention cleanup
        bytes_freed += self._delete_old_evidence()

        # Check threshold
        usage = self.get_usage_percent()
        if usage >= self._config.storage.max_usage_percent:
            logger.warning("Disk usage %.1f%% exceeds threshold %d%%",
                           usage, self._config.storage.max_usage_percent)
            bytes_freed += self._delete_non_violation_footage()

            # If still over threshold, delete oldest completed violations
            usage = self.get_usage_percent()
            if usage >= self._config.storage.max_usage_percent:
                bytes_freed += self._delete_oldest_completed()

        if bytes_freed > 0:
            logger.info("Storage cleanup freed %d bytes (%.1f MB)",
                        bytes_freed, bytes_freed / (1024 * 1024))

        return bytes_freed

    def _delete_old_evidence(self) -> int:
        """Delete evidence older than retention period."""
        retention_days = self._config.storage.evidence_retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_iso = cutoff.isoformat()

        deleted = self._db.delete_old_violations(cutoff_iso)
        bytes_freed = 0

        if deleted > 0:
            # Clean up orphaned evidence directories
            bytes_freed = self._cleanup_orphan_dirs()
            logger.info("Deleted %d old violations (retention: %d days)",
                        deleted, retention_days)

        return bytes_freed

    def _delete_non_violation_footage(self) -> int:
        """Delete non-violation data to free space.

        In a full implementation, this would delete raw footage that
        wasn't associated with any violation.
        """
        bytes_freed = 0
        # Delete discarded violation evidence
        discarded = self._db.get_violations_by_status("discarded")

        for violation in discarded:
            vid = violation["id"]
            evidence_path = self._evidence_dir / vid
            if evidence_path.exists():
                size = sum(f.stat().st_size for f in evidence_path.rglob("*") if f.is_file())
                shutil.rmtree(evidence_path, ignore_errors=True)
                bytes_freed += size

            self._db.update_violation_status(vid, "cleaned")

        if discarded:
            logger.info("Cleaned %d discarded violations, freed %d bytes",
                        len(discarded), bytes_freed)

        return bytes_freed

    def _delete_oldest_completed(self) -> int:
        """Delete oldest completed/sent violations when critically low on space."""
        bytes_freed = 0
        sent = self._db.get_violations_by_status("sent")

        # Delete oldest first (list is ordered by timestamp DESC, so reverse)
        for violation in reversed(sent):
            vid = violation["id"]
            evidence_path = self._evidence_dir / vid
            if evidence_path.exists():
                size = sum(f.stat().st_size for f in evidence_path.rglob("*") if f.is_file())
                shutil.rmtree(evidence_path, ignore_errors=True)
                bytes_freed += size

            self._db.update_violation_status(vid, "cleaned")

            # Check if we've freed enough
            if self.get_usage_percent() < self._config.storage.max_usage_percent:
                break

        return bytes_freed

    def _cleanup_orphan_dirs(self) -> int:
        """Remove evidence directories that have no matching DB record."""
        bytes_freed = 0

        if not self._evidence_dir.exists():
            return 0

        for entry in self._evidence_dir.iterdir():
            if not entry.is_dir():
                continue

            violation = self._db.get_violation(entry.name)
            if violation is None:
                size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                shutil.rmtree(entry, ignore_errors=True)
                bytes_freed += size
                logger.debug("Removed orphan evidence dir: %s", entry.name)

        return bytes_freed
