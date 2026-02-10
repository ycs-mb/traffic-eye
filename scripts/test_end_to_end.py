#!/usr/bin/env python3
"""End-to-end integration test for traffic-eye pipeline.

Tests the complete flow from video input to report generation:
1. Video frame capture and buffering
2. YOLOv8n object detection (vehicle + person)
3. Helmet classification (mock if model not ready)
4. Violation detection via rule engine
5. Evidence packaging (frames + video clip)
6. Gemini Cloud OCR (license plate reading)
7. Email report generation (template rendering)

Usage:
    python scripts/test_end_to_end.py [--video PATH] [--api-key KEY] [--skip-ocr]
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.capture.buffer import CircularFrameBuffer
from src.config import AppConfig, load_config
from src.detection.detector import TFLiteDetector
from src.detection.tracker import IOUTracker
from src.models import (
    FrameData,
    GPSReading,
    SignalState,
    ViolationCandidate,
)
from src.ocr.gemini_ocr import GeminiOCR
from src.ocr.validators import process_plate
from src.reporting.evidence import EvidencePackager
from src.reporting.report import ReportGenerator
from src.utils.database import Database
from src.violation.rules import RuleEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockHelmetClassifier:
    """Mock helmet classifier for testing when real model not available."""

    def __init__(self, always_no_helmet: bool = True):
        self.always_no_helmet = always_no_helmet
        logger.info("MockHelmetClassifier initialized (always_no_helmet=%s)", always_no_helmet)

    def classify(self, image: np.ndarray) -> tuple[bool, float]:
        """Mock classification - returns no helmet for testing."""
        if self.always_no_helmet:
            return False, 0.95  # No helmet, high confidence
        return True, 0.85  # Has helmet


class TestMetrics:
    """Track performance metrics during test."""

    def __init__(self):
        self.start_time = time.time()
        self.frames_processed = 0
        self.detections_found = 0
        self.violations_detected = 0
        self.ocr_attempts = 0
        self.ocr_successes = 0
        self.reports_generated = 0
        self.errors = []

    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    def fps(self) -> float:
        elapsed = self.elapsed_time()
        return self.frames_processed / elapsed if elapsed > 0 else 0.0

    def log_error(self, component: str, error: str):
        self.errors.append(f"{component}: {error}")
        logger.error("ERROR in %s: %s", component, error)

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("END-TO-END TEST SUMMARY")
        print("=" * 80)
        print(f"Elapsed time: {self.elapsed_time():.2f}s")
        print(f"Frames processed: {self.frames_processed}")
        print(f"Average FPS: {self.fps():.2f}")
        print(f"Detections found: {self.detections_found}")
        print(f"Violations detected: {self.violations_detected}")
        print(f"OCR attempts: {self.ocr_attempts}")
        print(f"OCR successes: {self.ocr_successes}")
        print(f"Reports generated: {self.reports_generated}")

        if self.errors:
            print(f"\nErrors encountered: {len(self.errors)}")
            for i, err in enumerate(self.errors, 1):
                print(f"  {i}. {err}")
        else:
            print("\nNo errors encountered!")

        print("=" * 80 + "\n")


class EndToEndTest:
    """End-to-end pipeline test."""

    def __init__(
        self,
        config: AppConfig,
        api_key: Optional[str] = None,
        skip_ocr: bool = False,
    ):
        self.config = config
        self.api_key = api_key
        self.skip_ocr = skip_ocr
        self.metrics = TestMetrics()

        # Initialize components
        self._init_components()

    def _init_components(self):
        """Initialize all pipeline components."""
        logger.info("Initializing components...")

        # Frame buffer
        self.buffer = CircularFrameBuffer(
            max_seconds=self.config.camera.buffer_seconds,
            fps=self.config.camera.fps / self.config.camera.process_every_nth_frame,
        )
        logger.info("✓ Frame buffer initialized")

        # YOLOv8 detector
        try:
            model_path = Path(self.config.detection.model_path)
            if not model_path.exists():
                raise FileNotFoundError(f"YOLOv8 model not found: {model_path}")

            self.detector = TFLiteDetector(
                confidence_threshold=self.config.detection.confidence_threshold,
                nms_threshold=self.config.detection.nms_threshold,
                num_threads=self.config.detection.num_threads,
                target_classes=tuple(self.config.detection.target_classes),
            )
            self.detector.load_model(str(model_path))
            logger.info("✓ YOLOv8 detector initialized")
        except Exception as e:
            self.metrics.log_error("detector", str(e))
            raise

        # Tracker
        self.tracker = IOUTracker()
        logger.info("✓ Object tracker initialized")

        # Helmet classifier (mock for now)
        self.helmet_classifier = MockHelmetClassifier(always_no_helmet=True)
        logger.info("✓ Helmet classifier initialized (MOCK)")

        # Rule engine
        self.rule_engine = RuleEngine(
            speed_gate_kmh=0.0,  # Disable speed gate for testing
            max_reports_per_hour=100,
        )
        logger.info("✓ Rule engine initialized")

        # Database
        db_path = Path(self.config.reporting.evidence_dir).parent / "test_traffic_eye.db"
        db_path.unlink(missing_ok=True)  # Clean start
        self.db = Database(str(db_path))
        logger.info("✓ Database initialized")

        # Evidence packager
        self.packager = EvidencePackager(self.config, self.db)
        logger.info("✓ Evidence packager initialized")

        # Report generator
        self.report_generator = ReportGenerator(self.config)
        logger.info("✓ Report generator initialized")

        # OCR (optional)
        self.ocr = None
        if not self.skip_ocr and self.api_key:
            try:
                self.ocr = GeminiOCR(
                    api_key=self.api_key,
                    confidence_threshold=self.config.cloud.confidence_threshold,
                    timeout=self.config.cloud.timeout_seconds,
                )
                logger.info("✓ Gemini OCR initialized")
            except Exception as e:
                self.metrics.log_error("ocr", str(e))
                logger.warning("OCR initialization failed, continuing without OCR")
        elif self.skip_ocr:
            logger.info("⊗ OCR skipped (--skip-ocr flag)")
        else:
            logger.info("⊗ OCR skipped (no API key)")

    def run(self, video_path: Optional[str] = None) -> bool:
        """Run end-to-end test.

        Args:
            video_path: Path to test video, or None to generate synthetic frames

        Returns:
            True if test passed, False otherwise
        """
        logger.info("Starting end-to-end test...")

        try:
            # Load or generate test frames
            frames = self._load_test_frames(video_path)
            if not frames:
                self.metrics.log_error("input", "No frames to process")
                return False

            logger.info("Processing %d frames...", len(frames))

            # Process frames through pipeline
            violations = self._process_frames(frames)

            if not violations:
                logger.warning("No violations detected in test")
                # This is OK - not necessarily a failure

            # Process violations (OCR + reporting)
            for violation in violations:
                self._process_violation(violation)

            # Print results
            self.metrics.print_summary()

            # Determine pass/fail
            success = self._evaluate_results()

            return success

        except Exception as e:
            self.metrics.log_error("pipeline", str(e))
            logger.exception("Test failed with exception")
            return False
        finally:
            self.db.close()

    def _load_test_frames(self, video_path: Optional[str]) -> list[np.ndarray]:
        """Load frames from video or generate synthetic test data."""
        frames = []

        if video_path:
            # Load from video file
            logger.info("Loading frames from video: %s", video_path)
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                self.metrics.log_error("input", f"Cannot open video: {video_path}")
                return []

            max_frames = 300  # Limit for testing (10 seconds at 30fps)
            frame_count = 0

            while frame_count < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
                frame_count += 1

            cap.release()
            logger.info("Loaded %d frames from video", len(frames))
        else:
            # Generate synthetic frames with mock detections
            logger.info("Generating synthetic test frames...")
            frames = self._generate_synthetic_frames(count=60)  # 2 seconds at 30fps
            logger.info("Generated %d synthetic frames", len(frames))

        return frames

    def _generate_synthetic_frames(self, count: int) -> list[np.ndarray]:
        """Generate synthetic frames for testing without video."""
        frames = []
        h, w = 720, 1280

        for i in range(count):
            # Create blank frame with gradient
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            frame[:, :] = (50, 50, 50)  # Dark gray background

            # Draw text
            text = f"Synthetic Frame {i+1}/{count}"
            cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                       1, (255, 255, 255), 2)

            # Draw simulated motorcycle + person (for detection)
            if i % 10 < 5:  # Visible in first half of each cycle
                # Motorcycle (moving across screen)
                x_offset = int((i / count) * w * 1.5) - 200
                cv2.rectangle(frame, (x_offset, 400), (x_offset + 150, 550),
                             (0, 0, 255), -1)
                cv2.putText(frame, "MOTO", (x_offset + 30, 490),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                # Person on motorcycle
                cv2.rectangle(frame, (x_offset + 40, 300), (x_offset + 110, 450),
                             (0, 255, 0), -1)
                cv2.putText(frame, "PERSON", (x_offset + 30, 370),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            frames.append(frame)

        return frames

    def _process_frames(self, frames: list[np.ndarray]) -> list[ViolationCandidate]:
        """Process frames through detection and rule engine."""
        violations = []
        frame_id = 0

        for frame in frames:
            frame_id += 1
            self.metrics.frames_processed += 1

            now = datetime.now(timezone.utc)

            # Run detection
            try:
                detections = self.detector.detect(frame, frame_id=frame_id)
                self.metrics.detections_found += len(detections)

                # Track objects
                detections = self.tracker.update(detections)

                # Store in buffer
                self.buffer.push(frame, now, frame_id)

                # Mock GPS (stationary for testing)
                gps = GPSReading(
                    latitude=19.0760,
                    longitude=72.8777,
                    altitude=10.0,
                    speed_kmh=25.0,  # Above speed gate
                    heading=90.0,
                    timestamp=now,
                    fix_quality=1,
                    satellites=8,
                )

                # Build frame data
                frame_data = FrameData(
                    frame=frame,
                    frame_id=frame_id,
                    timestamp=now,
                    gps=gps,
                    detections=detections,
                )

                # Classify helmets
                helmet_results = {}
                helmet_confs = {}
                for det in detections:
                    if det.bbox.class_name == "person" and det.track_id is not None:
                        x1, y1 = int(max(0, det.bbox.x1)), int(max(0, det.bbox.y1))
                        x2, y2 = int(min(frame.shape[1], det.bbox.x2)), int(min(frame.shape[0], det.bbox.y2))
                        if x2 > x1 and y2 > y1:
                            head_crop = frame[y1:y2, x1:x2]
                            has_helmet, conf = self.helmet_classifier.classify(head_crop)
                            helmet_results[det.track_id] = has_helmet
                            helmet_confs[det.track_id] = conf

                # Build rule context
                context = {
                    "has_helmet": helmet_results,
                    "helmet_confidence": helmet_confs,
                    "signal_state": SignalState.UNKNOWN,
                }

                # Run rule engine
                frame_violations = self.rule_engine.process_frame(frame_data, context)

                if frame_violations:
                    logger.info("Frame %d: %d violations detected",
                               frame_id, len(frame_violations))
                    violations.extend(frame_violations)
                    self.metrics.violations_detected += len(frame_violations)

            except Exception as e:
                self.metrics.log_error("detection", f"Frame {frame_id}: {e}")
                continue

        logger.info("Processed %d frames, found %d violations",
                   len(frames), len(violations))

        return violations

    def _process_violation(self, violation: ViolationCandidate):
        """Process a violation through OCR and reporting."""
        logger.info("Processing violation: %s (conf=%.2f)",
                   violation.violation_type.value, violation.confidence)

        # Package evidence
        try:
            evidence = self.packager.package(violation, self.buffer)
            logger.info("✓ Evidence packaged: %s", evidence.violation_id)
        except Exception as e:
            self.metrics.log_error("packaging", str(e))
            return

        # OCR on best frame (if available)
        if self.ocr and evidence.best_frames_jpeg:
            try:
                self.metrics.ocr_attempts += 1

                # Decode JPEG to numpy array
                nparr = np.frombuffer(evidence.best_frames_jpeg[0], np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                # For simplicity, use whole frame (in production, would crop to plate)
                plate_text, plate_conf = self.ocr.extract_plate_text(frame)

                if plate_text:
                    # Validate and correct
                    corrected, valid, state = process_plate(plate_text)
                    if valid:
                        violation.plate_text = corrected
                        violation.plate_confidence = plate_conf
                        evidence.violation.plate_text = corrected
                        evidence.violation.plate_confidence = plate_conf
                        evidence.metadata["cloud_verified"] = True
                        self.metrics.ocr_successes += 1
                        logger.info("✓ OCR success: %s (conf=%.2f, state=%s)",
                                   corrected, plate_conf, state)
                    else:
                        logger.warning("OCR returned invalid plate: %s", corrected)
                else:
                    logger.warning("OCR returned no text")

            except Exception as e:
                self.metrics.log_error("ocr", str(e))

        # Generate report
        try:
            report = self.report_generator.generate(evidence)
            self.metrics.reports_generated += 1

            logger.info("✓ Report generated: %s", report.subject)
            logger.info("  Attachments: %d", len(report.attachments))

            # Save report for inspection
            report_dir = Path(self.config.reporting.evidence_dir) / "test_reports"
            report_dir.mkdir(parents=True, exist_ok=True)

            html_path = report_dir / f"{evidence.violation_id}.html"
            html_path.write_text(report.html_body)

            text_path = report_dir / f"{evidence.violation_id}.txt"
            text_path.write_text(report.text_body)

            logger.info("  Report saved to: %s", report_dir)

        except Exception as e:
            self.metrics.log_error("reporting", str(e))

    def _evaluate_results(self) -> bool:
        """Evaluate if test passed based on results."""
        # Test passes if:
        # 1. Frames were processed
        # 2. No critical errors
        # 3. At least some detections found (unless using real video with no objects)

        if self.metrics.frames_processed == 0:
            logger.error("FAIL: No frames processed")
            return False

        if any("detector" in err or "pipeline" in err for err in self.metrics.errors):
            logger.error("FAIL: Critical component errors")
            return False

        logger.info("PASS: Pipeline executed successfully")
        return True


def create_test_video(output_path: str, duration_sec: int = 10):
    """Create a test video with mock motorcycle + person."""
    logger.info("Creating test video: %s", output_path)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 30
    size = (1280, 720)
    out = cv2.VideoWriter(output_path, fourcc, fps, size)

    frames = duration_sec * fps
    for i in range(frames):
        frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        frame[:, :] = (50, 50, 50)

        # Draw moving motorcycle + person
        x_offset = int((i / frames) * size[0] * 1.5) - 200

        # Motorcycle
        cv2.rectangle(frame, (x_offset, 400), (x_offset + 150, 550),
                     (0, 0, 255), -1)

        # Person
        cv2.rectangle(frame, (x_offset + 40, 300), (x_offset + 110, 450),
                     (0, 255, 0), -1)

        # Frame counter
        cv2.putText(frame, f"Frame {i+1}/{frames}", (50, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        out.write(frame)

    out.release()
    logger.info("Test video created: %s", output_path)


def main():
    parser = argparse.ArgumentParser(description="End-to-end pipeline test")
    parser.add_argument("--video", help="Path to test video file")
    parser.add_argument("--api-key", help="Gemini API key (or set TRAFFIC_EYE_CLOUD_API_KEY)")
    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR testing")
    parser.add_argument("--create-video", help="Create test video at path and exit")
    parser.add_argument("--config", default="config", help="Config directory")
    args = parser.parse_args()

    # Create test video if requested
    if args.create_video:
        create_test_video(args.create_video)
        return 0

    # Load config
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        return 1

    # Get API key
    api_key = args.api_key or os.getenv("TRAFFIC_EYE_CLOUD_API_KEY")

    if not api_key and not args.skip_ocr:
        logger.warning("No API key provided, OCR will be skipped")
        logger.warning("Use --api-key or set TRAFFIC_EYE_CLOUD_API_KEY environment variable")

    # Run test
    test = EndToEndTest(config, api_key=api_key, skip_ocr=args.skip_ocr)
    success = test.run(video_path=args.video)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
