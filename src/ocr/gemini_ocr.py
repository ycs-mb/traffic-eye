"""Cloud OCR using Gemini API for license plate reading."""

from __future__ import annotations

import base64
import json
import logging
from typing import Optional, Tuple

import cv2
import httpx
import numpy as np

logger = logging.getLogger(__name__)


class GeminiOCR:
    """Cloud OCR using Gemini API for license plate text extraction.

    Uses Google's Gemini 2.5 Flash model via the Generative Language API.
    More reliable and simpler than Vertex AI, with free tier available.
    """

    def __init__(
        self,
        api_key: str,
        confidence_threshold: float = 0.7,
        timeout: int = 30,
    ):
        """Initialize Gemini OCR.

        Args:
            api_key: Gemini API key from https://aistudio.google.com/app/apikey
            confidence_threshold: Minimum confidence to return result
            timeout: Request timeout in seconds
        """
        self._api_key = api_key
        self._confidence_threshold = confidence_threshold
        self._timeout = timeout
        self._model = "gemini-2.5-flash"

        logger.info(
            "GeminiOCR initialized (model=%s, threshold=%.2f)",
            self._model, confidence_threshold
        )

    def extract_plate_text(
        self,
        plate_image: np.ndarray,
    ) -> Tuple[Optional[str], float]:
        """Extract license plate text using Gemini API.

        Args:
            plate_image: Cropped plate region (numpy array, BGR format)

        Returns:
            Tuple of (plate_text, confidence) or (None, 0.0) on failure
        """
        try:
            # Convert numpy array to JPEG bytes
            success, buffer = cv2.imencode('.jpg', plate_image)
            if not success:
                logger.warning("Failed to encode plate image as JPEG")
                return None, 0.0

            image_b64 = base64.b64encode(buffer).decode()

            # Call Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self._api_key}"

            prompt = self._build_ocr_prompt()

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_b64,
                            }
                        },
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 200,
                },
            }

            response = httpx.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()

            result = response.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"]

            # Parse response
            return self._parse_ocr_response(text)

        except httpx.HTTPStatusError as e:
            logger.warning("Gemini API HTTP error %d: %s", e.response.status_code, e.response.text)
            return None, 0.0
        except Exception as e:
            logger.warning("Gemini OCR failed: %s", e)
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
        """Parse Gemini API OCR response.

        Args:
            text: Response text from Gemini API

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
                logger.debug("Gemini: plate not readable")
                return None, 0.0

            plate_text = data.get("plate_number", "").strip().upper()
            plate_text = plate_text.replace(" ", "").replace("-", "")  # Remove spaces/dashes
            confidence = float(data.get("confidence", 0.0))

            if not plate_text:
                return None, 0.0

            if confidence < self._confidence_threshold:
                logger.debug(
                    "Gemini: confidence %.2f below threshold %.2f",
                    confidence, self._confidence_threshold
                )
                return None, confidence

            logger.info("Gemini OCR extracted: %s (conf=%.2f)", plate_text, confidence)
            return plate_text, confidence

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse Gemini OCR response: %s", e)
            logger.debug("Raw response: %s", text)
            return None, 0.0


def create_gemini_ocr(
    api_key: str,
    confidence_threshold: float = 0.7,
    timeout: int = 30,
) -> GeminiOCR:
    """Factory function to create GeminiOCR instance.

    Args:
        api_key: Gemini API key
        confidence_threshold: Minimum confidence threshold
        timeout: Request timeout

    Returns:
        GeminiOCR instance
    """
    return GeminiOCR(
        api_key=api_key,
        confidence_threshold=confidence_threshold,
        timeout=timeout,
    )
