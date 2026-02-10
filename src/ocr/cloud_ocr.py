"""Cloud-only OCR using Vertex AI for license plate reading."""

from __future__ import annotations

import json
import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class CloudOCR:
    """Cloud-only OCR that delegates all plate reading to Vertex AI.

    This bypasses local OCR entirely and sends plate regions directly
    to GCP Vertex AI for text extraction. More accurate than local OCR
    but requires network connectivity and incurs API costs.
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        confidence_threshold: float = 0.7,
    ):
        """Initialize Cloud OCR.

        Args:
            project_id: GCP project ID
            location: GCP region (default: us-central1)
            confidence_threshold: Minimum confidence to return result
        """
        self._project_id = project_id
        self._location = location
        self._confidence_threshold = confidence_threshold
        self._model = None

        logger.info(
            "CloudOCR initialized (project=%s, location=%s, threshold=%.2f)",
            project_id, location, confidence_threshold
        )

    def _init_model(self):
        """Lazy initialization of Vertex AI model."""
        if self._model is not None:
            return

        try:
            from google.cloud import aiplatform
            from vertexai.generative_models import GenerativeModel

            aiplatform.init(project=self._project_id, location=self._location)
            # Use Gemini 1.5 Flash (faster, cheaper, supports vision)
            self._model = GenerativeModel("gemini-1.5-flash")
            logger.info("Vertex AI Gemini model initialized")

        except ImportError as e:
            logger.error("Vertex AI SDK not installed: %s", e)
            logger.error("Install with: pip install google-cloud-aiplatform")
            raise
        except Exception as e:
            logger.error("Failed to initialize Vertex AI: %s", e)
            raise

    def extract_plate_text(
        self,
        plate_image: np.ndarray,
    ) -> Tuple[Optional[str], float]:
        """Extract license plate text using Vertex AI.

        Args:
            plate_image: Cropped plate region (numpy array, BGR format)

        Returns:
            Tuple of (plate_text, confidence) or (None, 0.0) on failure
        """
        try:
            self._init_model()

            # Convert numpy array to JPEG bytes
            import cv2
            success, buffer = cv2.imencode('.jpg', plate_image)
            if not success:
                logger.warning("Failed to encode plate image as JPEG")
                return None, 0.0

            image_bytes = buffer.tobytes()

            # Create prompt for plate OCR
            prompt = self._build_ocr_prompt()

            # Call Vertex AI
            from vertexai.preview.generative_models import Part
            image_part = Part.from_data(image_bytes, mime_type="image/jpeg")

            response = self._model.generate_content(
                [prompt, image_part],
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 200,
                }
            )

            # Parse response
            return self._parse_ocr_response(response.text)

        except Exception as e:
            logger.warning("Cloud OCR failed: %s", e)
            return None, 0.0

    def _build_ocr_prompt(self) -> str:
        """Build prompt for license plate OCR."""
        return (
            "Extract the license plate number from this image. "
            "Return ONLY a JSON object with these fields:\n"
            "- plate_number: string (the plate text, uppercase, no spaces)\n"
            "- confidence: float (0.0 to 1.0, your confidence in the reading)\n"
            "- readable: boolean (true if plate is clearly readable)\n\n"
            "Indian license plates format: MH12AB1234 or similar.\n"
            "If the plate is not readable or not present, set readable=false.\n"
            "Return ONLY the JSON, no other text."
        )

    def _parse_ocr_response(self, text: str) -> Tuple[Optional[str], float]:
        """Parse Vertex AI OCR response.

        Args:
            text: Response text from Vertex AI

        Returns:
            Tuple of (plate_text, confidence)
        """
        try:
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text.strip())

            if not data.get("readable", False):
                logger.debug("Vertex AI: plate not readable")
                return None, 0.0

            plate_text = data.get("plate_number", "").strip().upper()
            confidence = float(data.get("confidence", 0.0))

            if not plate_text:
                return None, 0.0

            if confidence < self._confidence_threshold:
                logger.debug(
                    "Vertex AI: confidence %.2f below threshold %.2f",
                    confidence, self._confidence_threshold
                )
                return None, confidence

            logger.info("Cloud OCR extracted: %s (conf=%.2f)", plate_text, confidence)
            return plate_text, confidence

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse Vertex AI OCR response: %s", e)
            logger.debug("Raw response: %s", text)
            return None, 0.0


def create_cloud_ocr(
    project_id: str,
    location: str = "us-central1",
    confidence_threshold: float = 0.7,
) -> CloudOCR:
    """Factory function to create CloudOCR instance.

    Args:
        project_id: GCP project ID
        location: GCP region
        confidence_threshold: Minimum confidence threshold

    Returns:
        CloudOCR instance
    """
    return CloudOCR(
        project_id=project_id,
        location=location,
        confidence_threshold=confidence_threshold,
    )
