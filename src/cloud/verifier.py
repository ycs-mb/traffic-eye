"""Cloud verification via GPT-4V or Gemini Vision API."""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import httpx

from src.config import AppConfig
from src.models import EvidencePacket

if TYPE_CHECKING:
    from src.cloud.queue import CloudQueue
    from src.utils.database import Database

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result from cloud verification API."""
    confirmed: bool
    confidence: float
    violation_type: Optional[str] = None
    plate_text: Optional[str] = None
    raw_response: dict = field(default_factory=dict)


class CloudVerifier:
    """Sends evidence to GPT-4V or Gemini Vision API for verification.

    Constructs a prompt with the best evidence frame as a base64 image,
    sends to the configured API, and parses the structured response.
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._provider = config.cloud.provider
        self._timeout = config.cloud.timeout_seconds
        self._max_retries = config.cloud.max_retries

    def verify(self, evidence: EvidencePacket) -> VerificationResult:
        """Send evidence to cloud API for verification.

        Args:
            evidence: Evidence packet with frames to verify.

        Returns:
            VerificationResult with API response.
        """
        api_key = self._config.cloud.api_key
        if not api_key and self._provider != "vertex_ai":
            logger.warning("Cloud API key not configured")
            return VerificationResult(confirmed=False, confidence=0.0)

        if not evidence.best_frames_jpeg:
            logger.warning("No frames in evidence packet")
            return VerificationResult(confirmed=False, confidence=0.0)

        # Use the first (best) frame
        image_b64 = base64.b64encode(evidence.best_frames_jpeg[0]).decode()
        prompt = self._build_prompt(evidence)

        for attempt in range(1, self._max_retries + 1):
            try:
                if self._provider == "gemini":
                    raw = self._call_gemini(api_key, image_b64, prompt)
                elif self._provider == "openai":
                    raw = self._call_openai(api_key, image_b64, prompt)
                elif self._provider == "vertex_ai":
                    raw = self._call_vertex_ai(image_b64, prompt)
                else:
                    logger.error("Unknown cloud provider: %s", self._provider)
                    return VerificationResult(confirmed=False, confidence=0.0)

                return self._parse_response(raw)

            except httpx.TimeoutException:
                logger.warning("Cloud API timeout (attempt %d/%d)", attempt, self._max_retries)
            except httpx.HTTPStatusError as e:
                logger.warning("Cloud API HTTP error %d (attempt %d/%d)",
                               e.response.status_code, attempt, self._max_retries)
            except Exception as e:
                logger.warning("Cloud API error: %s (attempt %d/%d)",
                               e, attempt, self._max_retries)

            if attempt < self._max_retries:
                backoff = 2 ** attempt
                time.sleep(backoff)

        return VerificationResult(confirmed=False, confidence=0.0)

    def _build_prompt(self, evidence: EvidencePacket) -> str:
        """Build the verification prompt."""
        vtype = evidence.metadata.get("violation_type", "unknown")
        return (
            "Analyze this traffic camera image. Answer in JSON format with these fields:\n"
            "- is_violation: boolean (true if a traffic violation is visible)\n"
            f"- violation_type: string (expected: '{vtype}', or 'none')\n"
            "- confidence: float (0.0 to 1.0)\n"
            "- plate_number: string or null (vehicle license plate if readable)\n"
            "- description: string (brief description of what you see)\n\n"
            "Focus on: Is there a clear traffic violation? Can you read any license plates?"
        )

    def _call_gemini(self, api_key: str, image_b64: str, prompt: str) -> dict:
        """Call Gemini Vision API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

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
                "maxOutputTokens": 500,
            },
        }

        response = httpx.post(url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def _call_openai(self, api_key: str, image_b64: str, prompt: str) -> dict:
        """Call OpenAI GPT-4V API."""
        url = "https://api.openai.com/v1/chat/completions"

        payload = {
            "model": "gpt-4-vision-preview",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                ],
            }],
            "max_tokens": 500,
            "temperature": 0.1,
        }

        headers = {"Authorization": f"Bearer {api_key}"}
        response = httpx.post(url, json=payload, headers=headers, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def _call_vertex_ai(self, image_b64: str, prompt: str) -> dict:
        """Call GCP Vertex AI Gemini API.

        Uses Application Default Credentials (ADC) from environment.
        Requires GOOGLE_APPLICATION_CREDENTIALS or gcloud auth.
        """
        import os
        from google.cloud import aiplatform
        from vertexai.generative_models import GenerativeModel, Part

        # Get project and location from environment or config
        project_id = os.environ.get("GCP_PROJECT_ID", self._config.cloud.gcp_project_id)
        location = os.environ.get("GCP_LOCATION", self._config.cloud.gcp_location)

        if not project_id:
            raise ValueError("GCP_PROJECT_ID not configured")

        # Initialize Vertex AI
        aiplatform.init(project=project_id, location=location)

        # Use Gemini 1.5 Flash (faster, cheaper, supports vision)
        model = GenerativeModel("gemini-1.5-flash")

        # Decode base64 image
        image_bytes = base64.b64decode(image_b64)
        image_part = Part.from_data(image_bytes, mime_type="image/jpeg")

        # Generate content
        response = model.generate_content(
            [prompt, image_part],
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 500,
            }
        )

        # Format response to match expected structure
        return {
            "candidates": [{
                "content": {
                    "parts": [{"text": response.text}]
                }
            }]
        }

    def _parse_response(self, raw: dict) -> VerificationResult:
        """Parse cloud API response into VerificationResult."""
        try:
            # Extract text content based on provider format
            text = ""
            if "candidates" in raw:
                # Gemini format
                parts = raw["candidates"][0]["content"]["parts"]
                text = parts[0]["text"]
            elif "choices" in raw:
                # OpenAI format
                text = raw["choices"][0]["message"]["content"]

            # Try to parse JSON from the response text
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text.strip())

            return VerificationResult(
                confirmed=data.get("is_violation", False),
                confidence=float(data.get("confidence", 0.0)),
                violation_type=data.get("violation_type"),
                plate_text=data.get("plate_number"),
                raw_response=raw,
            )

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning("Failed to parse cloud response: %s", e)
            return VerificationResult(
                confirmed=False,
                confidence=0.0,
                raw_response=raw,
            )


class CloudVerificationProcessor:
    """Processes the cloud verification queue.

    Runs as a background task, checking the queue periodically.
    """

    def __init__(
        self,
        config: AppConfig,
        db: 'Database',
        queue: CloudQueue,
        verifier: CloudVerifier,
    ):
        self._config = config
        self._db = db
        self._queue = queue
        self._verifier = verifier

    def process_batch(self) -> int:
        """Process pending cloud verification requests.

        Returns:
            Number of items processed.
        """
        if not self._queue.is_online():
            logger.debug("No connectivity, skipping cloud verification")
            return 0

        pending = self._queue.get_pending(limit=5)
        processed = 0

        for entry in pending:
            queue_id = entry["id"]
            violation_id = entry["violation_id"]

            violation = self._db.get_violation(violation_id)
            if not violation:
                self._queue.mark_failed(queue_id, "Violation not found")
                processed += 1
                continue

            # Get evidence files
            evidence_files = self._db.get_evidence_files(violation_id)
            if not evidence_files:
                self._queue.mark_failed(queue_id, "No evidence files")
                processed += 1
                continue

            # Build a minimal evidence packet for verification
            frames_jpeg = []
            for ef in evidence_files:
                if ef["file_type"] == "frame":
                    try:
                        from pathlib import Path
                        frames_jpeg.append(Path(ef["file_path"]).read_bytes())
                    except FileNotFoundError:
                        continue

            evidence = EvidencePacket(
                violation_id=violation_id,
                best_frames_jpeg=frames_jpeg,
                metadata={
                    "violation_type": violation["type"],
                    "confidence": violation["confidence"],
                },
            )

            result = self._verifier.verify(evidence)

            if result.confirmed and result.confidence >= self._config.cloud.confidence_threshold:
                self._queue.mark_complete(queue_id, result.raw_response)
                self._db.update_violation_status(violation_id, "verified")
                logger.info("Cloud verification confirmed: %s (conf=%.2f)",
                            violation_id, result.confidence)

                # Queue email for verified violation
                self._db.enqueue_email(violation_id)
            else:
                self._queue.mark_failed(
                    queue_id,
                    f"Not confirmed (conf={result.confidence:.2f})"
                )
                self._db.update_violation_status(violation_id, "discarded")
                logger.info("Cloud verification rejected: %s", violation_id)

            processed += 1

        return processed
