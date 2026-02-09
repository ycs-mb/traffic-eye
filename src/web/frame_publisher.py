"""
Frame publisher for sending frames from detection loop to dashboard.
Uses HTTP POST to push frames to the dashboard server.
"""

import cv2
import base64
import requests
import numpy as np
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class FramePublisher:
    """Publishes detection frames to the dashboard."""

    def __init__(self, dashboard_url: str = "http://localhost:8080"):
        self.dashboard_url = dashboard_url
        self.enabled = True
        self._check_dashboard()

    def _check_dashboard(self):
        """Check if dashboard is available."""
        try:
            response = requests.get(f"{self.dashboard_url}/api/status", timeout=1)
            self.enabled = response.status_code == 200
            if self.enabled:
                logger.info("Dashboard connection established")
        except Exception as e:
            logger.warning(f"Dashboard not available: {e}")
            self.enabled = False

    def publish_frame(self, frame: np.ndarray, detections: Optional[List[dict]] = None):
        """
        Publish a frame with detections to the dashboard.

        Args:
            frame: BGR image from OpenCV
            detections: List of detection dicts with keys: x1, y1, x2, y2, class_name, confidence
        """
        if not self.enabled:
            return

        try:
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                return

            # Convert to base64
            frame_b64 = base64.b64encode(buffer).decode('utf-8')

            # Prepare detections data
            detection_data = []
            if detections:
                for det in detections:
                    if hasattr(det, 'bbox'):
                        # Detection object from models.py
                        detection_data.append({
                            'x1': det.bbox.x1,
                            'y1': det.bbox.y1,
                            'x2': det.bbox.x2,
                            'y2': det.bbox.y2,
                            'class_name': det.bbox.class_name,
                            'confidence': det.bbox.confidence
                        })
                    elif isinstance(det, dict):
                        # Already a dict
                        detection_data.append(det)

            # Send to dashboard
            payload = {
                'frame_b64': frame_b64,
                'detections': detection_data
            }

            response = requests.post(
                f"{self.dashboard_url}/api/update_frame",
                json=payload,
                timeout=0.5
            )

            if response.status_code != 200:
                logger.warning(f"Dashboard update failed: {response.status_code}")

        except requests.exceptions.Timeout:
            # Dashboard busy, skip this frame
            pass
        except Exception as e:
            logger.debug(f"Frame publish error: {e}")


class MockFramePublisher:
    """Mock publisher that does nothing (for when dashboard is disabled)."""

    def __init__(self, *args, **kwargs):
        pass

    def publish_frame(self, frame: np.ndarray, detections: Optional[List[dict]] = None):
        pass
