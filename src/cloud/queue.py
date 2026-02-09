"""Offline queue manager for cloud verification requests."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from src.config import AppConfig
from src.models import EvidencePacket
from src.utils.database import Database

logger = logging.getLogger(__name__)


class CloudQueue:
    """Manages offline queue of verification requests.

    When a violation has confidence between 0.70 and 0.96,
    it is queued for cloud verification. The queue persists in SQLite.
    Processing happens when connectivity is available.
    """

    def __init__(self, config: AppConfig, db: Database):
        self._config = config
        self._db = db
        self._connectivity_url = "https://www.google.com/generate_204"

    def enqueue(self, violation_id: str) -> int:
        """Add a violation to the cloud verification queue.

        Args:
            violation_id: ID of the violation to verify.

        Returns:
            Queue entry ID.
        """
        queue_id = self._db.enqueue_cloud(violation_id)
        logger.info("Queued violation %s for cloud verification (queue_id=%d)",
                     violation_id, queue_id)
        return queue_id

    def get_pending(self, limit: int = 10) -> list[dict]:
        """Get pending verification requests."""
        return self._db.get_pending_cloud(limit=limit)

    def mark_complete(self, queue_id: int, response: dict) -> None:
        """Mark a queue entry as successfully verified."""
        import json
        self._db.update_cloud_status(
            queue_id, "done",
            response_json=json.dumps(response),
        )

    def mark_failed(self, queue_id: int, error: str) -> None:
        """Mark a queue entry as failed."""
        self._db.update_cloud_status(
            queue_id, "failed",
            error_message=error,
        )

    def is_online(self) -> bool:
        """Check internet connectivity by pinging a known endpoint."""
        try:
            response = httpx.head(self._connectivity_url, timeout=5.0)
            return response.status_code in (200, 204)
        except (httpx.HTTPError, httpx.TimeoutException):
            return False
