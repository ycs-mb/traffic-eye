"""Evidence packaging for violation reports."""

from __future__ import annotations

import hashlib
import logging
import subprocess
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from src.capture.buffer import CircularFrameBuffer
from src.config import AppConfig
from src.models import (
    EvidencePacket,
    GPSReading,
    ViolationCandidate,
)
from src.utils.database import Database
from src.utils.geocoder import ReverseGeocoder

logger = logging.getLogger(__name__)


class EvidencePackager:
    """Creates evidence packets from violation candidates.

    Steps:
    1. Select best N frames (highest confidence) from buffer
    2. Annotate frames with bounding boxes and metadata
    3. Encode frames as JPEG
    4. Generate video clip from frame sequence
    5. Compute SHA256 hashes for integrity
    6. Persist to database and filesystem
    """

    def __init__(self, config: AppConfig, db: Database,
                 geocoder: Optional[ReverseGeocoder] = None):
        self._config = config
        self._db = db
        self._geocoder = geocoder
        self._evidence_dir = Path(config.reporting.evidence_dir)
        self._evidence_dir.mkdir(parents=True, exist_ok=True)

    def package(
        self,
        violation: ViolationCandidate,
        buffer: CircularFrameBuffer,
    ) -> EvidencePacket:
        """Create a complete evidence packet.

        Args:
            violation: The violation candidate to package.
            buffer: Frame buffer to extract clip from.

        Returns:
            EvidencePacket with all evidence data.
        """
        violation_id = str(uuid.uuid4())
        evidence_path = self._evidence_dir / violation_id
        evidence_path.mkdir(parents=True, exist_ok=True)

        # Extract and select frames
        clip_frames = self._extract_clip_frames(violation, buffer)
        best_frames = self._select_best_frames(
            violation, clip_frames, self._config.reporting.best_frames_count
        )

        # Build metadata (needed for GPS address in violation record)
        metadata = self._build_metadata(violation, clip_frames, best_frames)

        # Persist violation first (to satisfy FK constraints for evidence files)
        gps_address = metadata.get("gps", {}).get("address")
        self._persist_violation(violation_id, violation, gps_address)

        # Process frames and video
        best_frames_jpeg, file_hashes = self._process_frames(
            violation_id, evidence_path, violation, best_frames
        )
        video_path = self._process_video(
            violation_id, evidence_path, clip_frames, file_hashes
        )

        packet = EvidencePacket(
            violation_id=violation_id,
            violation=violation,
            best_frames_jpeg=best_frames_jpeg,
            video_clip_path=video_path,
            metadata=metadata,
            file_hashes=file_hashes,
        )

        logger.info(
            "Evidence packaged: %s (%s, conf=%.2f, frames=%d)",
            violation_id, violation.violation_type.value,
            violation.confidence, len(best_frames_jpeg),
        )
        return packet

    def _extract_clip_frames(
        self, violation: ViolationCandidate, buffer: CircularFrameBuffer
    ) -> list:
        """Extract clip frames from buffer based on timing."""
        clip_before = self._config.reporting.clip_before_seconds
        clip_after = self._config.reporting.clip_after_seconds
        start_time = violation.timestamp - timedelta(seconds=clip_before)
        end_time = violation.timestamp + timedelta(seconds=clip_after)
        return buffer.get_clip(start_time, end_time)

    def _process_frames(
        self, violation_id: str, evidence_path: Path,
        violation: ViolationCandidate, best_frames: list
    ) -> tuple[list[bytes], dict[str, str]]:
        """Encode frames to JPEG and return data with hashes."""
        best_frames_jpeg = []
        file_hashes = {}

        for i, bf in enumerate(best_frames):
            try:
                annotated = self._annotate_frame(bf.frame.copy(), violation)
                tmp_jpeg = Path(f"/tmp/frame_{violation_id}_{i:02d}.jpg")
                cv2.imwrite(str(tmp_jpeg), annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])

                jpeg_data = tmp_jpeg.read_bytes()
                file_hash = self._compute_hash(jpeg_data)
                final_jpeg = evidence_path / f"frame_{i:02d}.jpg"
                self._atomic_move(str(tmp_jpeg), str(final_jpeg))

                best_frames_jpeg.append(jpeg_data)
                file_hashes[f"frame_{i:02d}.jpg"] = file_hash
                self._db.insert_evidence_file(
                    violation_id, str(final_jpeg), "frame", len(jpeg_data), file_hash
                )
            except Exception as e:
                logger.error("Frame encoding failed (frame %d): %s", i, e)

        return best_frames_jpeg, file_hashes

    def _process_video(
        self, violation_id: str, evidence_path: Path,
        clip_frames: list, file_hashes: dict[str, str]
    ) -> Optional[str]:
        """Encode video clip and return path if successful."""
        if not clip_frames:
            return None

        try:
            video_path = str(evidence_path / "clip.mp4")
            raw_frames = [bf.frame for bf in clip_frames]
            self._encode_video_clip(raw_frames, video_path)

            if Path(video_path).exists():
                video_data = Path(video_path).read_bytes()
                video_hash = self._compute_hash(video_data)
                file_hashes["clip.mp4"] = video_hash
                self._db.insert_evidence_file(
                    violation_id, video_path, "video", len(video_data), video_hash
                )
                return video_path
        except Exception as e:
            logger.error("Video encoding failed: %s", e)

        return None

    def _build_metadata(
        self, violation: ViolationCandidate, clip_frames: list, best_frames: list
    ) -> dict:
        """Build evidence metadata dictionary."""
        metadata = {
            "violation_type": violation.violation_type.value,
            "confidence": violation.confidence,
            "timestamp": violation.timestamp.isoformat(),
            "consecutive_frames": violation.consecutive_frame_count,
            "clip_frame_count": len(clip_frames),
            "best_frame_count": len(best_frames),
        }

        if violation.gps:
            metadata["gps"] = self._build_gps_metadata(violation.gps)
        if violation.plate_text:
            metadata["plate_text"] = violation.plate_text
            metadata["plate_confidence"] = violation.plate_confidence

        return metadata

    def _build_gps_metadata(self, gps: GPSReading) -> dict:
        """Build GPS metadata with optional reverse geocoding."""
        gps_data = {
            "lat": gps.latitude,
            "lon": gps.longitude,
            "speed_kmh": gps.speed_kmh,
            "heading": gps.heading,
        }

        if self._geocoder:
            try:
                geo = self._geocoder.reverse(gps.latitude, gps.longitude)
                if geo:
                    gps_data["address"] = geo.medium_address
                    gps_data["address_short"] = geo.short_address
                    gps_data["address_full"] = geo.full_address
            except Exception as e:
                logger.warning("Geocoding failed: %s", e)

        return gps_data

    def _persist_violation(
        self, violation_id: str, violation: ViolationCandidate, gps_address: Optional[str]
    ) -> None:
        """Persist violation record to database."""
        self._db.insert_violation(
            violation_id=violation_id,
            violation_type=violation.violation_type.value,
            confidence=violation.confidence,
            plate_text=violation.plate_text,
            plate_confidence=violation.plate_confidence,
            gps_lat=violation.gps.latitude if violation.gps else None,
            gps_lon=violation.gps.longitude if violation.gps else None,
            gps_heading=violation.gps.heading if violation.gps else None,
            gps_speed_kmh=violation.gps.speed_kmh if violation.gps else None,
            gps_address=gps_address,
            timestamp=violation.timestamp.isoformat(),
            consecutive_frames=violation.consecutive_frame_count,
        )

    def _select_best_frames(
        self,
        violation: ViolationCandidate,
        clip_frames,
        count: int,
    ) -> list:
        """Select the N frames with highest aggregate detection confidence."""
        if not clip_frames:
            return []

        # Build a map of frame_id to confidence score
        frame_scores = {}
        if violation.frames:
            for fd in violation.frames:
                total_conf = sum(
                    d.bbox.confidence for d in fd.detections
                ) if fd.detections else 0.0
                frame_scores[fd.frame_id] = total_conf

        # Score all clip frames
        scored = []
        for bf in clip_frames:
            score = frame_scores.get(bf.frame_id, 0.0)
            scored.append((bf, score))

        # Sort by score descending and return top N
        scored.sort(key=lambda x: x[1], reverse=True)
        return [bf for bf, _ in scored[:count]]

    def _annotate_frame(
        self, frame: np.ndarray, violation: ViolationCandidate
    ) -> np.ndarray:
        """Draw bounding boxes, labels, and metadata on a frame."""
        self._draw_detections(frame, violation)
        self._draw_metadata_overlay(frame, violation)
        return frame

    def _draw_detections(
        self, frame: np.ndarray, violation: ViolationCandidate
    ) -> None:
        """Draw detection bounding boxes on frame."""
        if not (violation.best_frame and violation.best_frame.detections):
            return

        for det in violation.best_frame.detections:
            bbox = det.bbox
            x1, y1, x2, y2 = int(bbox.x1), int(bbox.y1), int(bbox.x2), int(bbox.y2)
            is_violation = "motorcycle" in bbox.class_name or "person" in bbox.class_name
            color = (0, 0, 255) if is_violation else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{bbox.class_name} {bbox.confidence:.2f}"
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    def _draw_metadata_overlay(
        self, frame: np.ndarray, violation: ViolationCandidate
    ) -> None:
        """Draw metadata overlay at bottom of frame."""
        h, w = frame.shape[:2]
        overlay_h = 40
        cv2.rectangle(frame, (0, h - overlay_h), (w, h), (0, 0, 0), -1)

        text_parts = [
            f"TYPE: {violation.violation_type.value}",
            f"CONF: {violation.confidence:.2f}",
        ]
        if violation.gps:
            text_parts.append(f"GPS: {violation.gps.latitude:.4f},{violation.gps.longitude:.4f}")
        if violation.plate_text:
            text_parts.append(f"PLATE: {violation.plate_text}")

        text = " | ".join(text_parts)
        cv2.putText(frame, text, (5, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    def _encode_video_clip(
        self, frames: list[np.ndarray], output_path: str, fps: float = 8.0
    ) -> None:
        """Encode frames into H.264 MP4 with Pi optimization.

        Uses tmpfs and hardware acceleration when available.
        """
        if not frames:
            return

        h, w = frames[0].shape[:2]
        tmp_path = f"/tmp/clip_{uuid.uuid4().hex}.mp4"

        try:
            if self._encode_with_fallback(frames, tmp_path, w, h, fps):
                self._atomic_move(tmp_path, output_path)
                logger.debug("Video encoded: %s", output_path)
            else:
                logger.warning("Video encoding failed: %s", output_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _encode_with_fallback(
        self, frames: list[np.ndarray], output: str, w: int, h: int, fps: float
    ) -> bool:
        """Try hardware encoding, fall back to software."""
        if self._try_hw_encode(frames, output, w, h, fps):
            logger.debug("HW encoding succeeded")
            return True
        if self._try_sw_encode(frames, output, w, h, fps):
            logger.debug("SW encoding succeeded")
            return True
        return False

    def _try_hw_encode(
        self, frames: list[np.ndarray], output: str,
        w: int, h: int, fps: float
    ) -> bool:
        """Try hardware-accelerated H.264 encoding via V4L2 M2M."""
        try:
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "rawvideo", "-vcodec", "rawvideo",
                "-s", f"{w}x{h}", "-pix_fmt", "bgr24", "-r", str(fps),
                "-i", "-",
                "-c:v", "h264_v4l2m2m",
                "-b:v", "1M", "-maxrate", "1.5M", "-bufsize", "2M",
                "-pix_fmt", "yuv420p", output,
            ]
            proc = subprocess.run(
                cmd, input=b"".join(f.tobytes() for f in frames),
                capture_output=True, timeout=60,
            )
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _try_sw_encode(
        self, frames: list[np.ndarray], output: str,
        w: int, h: int, fps: float
    ) -> bool:
        """Software H.264 encoding with libx264."""
        try:
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "rawvideo", "-vcodec", "rawvideo",
                "-s", f"{w}x{h}", "-pix_fmt", "bgr24", "-r", str(fps),
                "-i", "-",
                "-c:v", "libx264", "-preset", "fast",
                "-crf", "28", "-pix_fmt", "yuv420p", output,
            ]
            proc = subprocess.run(
                cmd, input=b"".join(f.tobytes() for f in frames),
                capture_output=True, timeout=60,
            )
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _atomic_move(src: str, dst: str) -> None:
        """Atomically move file (minimize SD card corruption risk)."""
        import shutil
        dst_path = Path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dst)

    @staticmethod
    def _compute_hash(data: bytes) -> str:
        """Compute SHA256 hash of data."""
        return hashlib.sha256(data).hexdigest()
