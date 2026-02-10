"""Main entry point and orchestrator for traffic-eye."""

from __future__ import annotations

import argparse
import logging
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from src.capture.buffer import CircularFrameBuffer
from src.config import AppConfig, load_config
from src.detection.signal import TrafficSignalClassifier
from src.detection.tracker import IOUTracker
from src.models import FrameData, SignalState
from src.platform_factory import (
    create_camera,
    create_detector,
    create_gps,
    create_helmet_classifier,
    create_thermal_monitor,
)
from src.utils.database import Database
from src.utils.logging_config import setup_logging
from src.violation.rules import RuleEngine

logger = logging.getLogger(__name__)


class TrafficEyeApp:
    """Main application orchestrator."""

    def __init__(self, config: AppConfig, video_file: str | None = None):
        self._config = config
        self._running = False
        self._frame_id = 0
        self._last_save_time = 0.0

        # Create components via platform factory
        self._camera = create_camera(config, video_file=video_file)
        self._gps = create_gps(config)
        self._detector = create_detector(config)
        self._helmet_classifier = create_helmet_classifier(config)
        self._thermal = create_thermal_monitor(config)
        self._signal_classifier = TrafficSignalClassifier()
        self._tracker = IOUTracker()

        # Database
        db_path = str(Path(config.reporting.evidence_dir).parent / "traffic_eye.db")
        self._db = Database(db_path)

        # Capture directory for saving frames
        self._capture_dir = Path(config.reporting.evidence_dir).parent / "captures"
        self._capture_dir.mkdir(parents=True, exist_ok=True)

        # Frame buffer (at processing rate, not raw fps)
        effective_fps = config.camera.fps / config.camera.process_every_nth_frame
        self._buffer = CircularFrameBuffer(
            max_seconds=config.camera.buffer_seconds,
            fps=effective_fps,
        )

        # Rule engine
        # Load rule configs from violation_rules.yaml
        self._rule_engine = RuleEngine(
            speed_gate_kmh=config.gps.speed_gate_kmh,
            max_reports_per_hour=config.violations.max_reports_per_hour,
        )

    def run(self) -> None:
        """Run the main detection loop."""
        self._running = True
        raw_frame_count = 0
        nth = self._config.camera.process_every_nth_frame

        logger.info("Starting traffic-eye detection loop")

        try:
            self._camera.open()
            self._gps.start()

            while self._running:
                # Thermal check
                if self._thermal.should_pause(self._config.thermal.pause_temp_c):
                    logger.warning("CPU too hot (%.1fC), pausing for %ds",
                                   self._thermal.get_cpu_temp(),
                                   self._config.thermal.pause_duration_seconds)
                    time.sleep(self._config.thermal.pause_duration_seconds)
                    continue

                # Read frame
                frame = self._camera.read_frame()
                if frame is None:
                    break

                raw_frame_count += 1

                # Process every Nth frame
                if raw_frame_count % nth != 0:
                    continue

                # Throttle if needed
                process_nth = nth
                if self._thermal.should_throttle(self._config.thermal.throttle_temp_c):
                    process_nth = nth * 2  # Skip more frames
                    if raw_frame_count % process_nth != 0:
                        continue

                now = datetime.now(timezone.utc)
                gps_reading = self._gps.get_reading()

                # Run detection
                detections = self._detector.detect(frame, frame_id=self._frame_id)

                # Track objects
                detections = self._tracker.update(detections)

                # Build frame data
                frame_data = FrameData(
                    frame=frame,
                    frame_id=self._frame_id,
                    timestamp=now,
                    gps=gps_reading,
                    detections=detections,
                )

                # Store in buffer
                self._buffer.push(frame, now, self._frame_id)

                # Save a frame every second
                current_time = time.monotonic()
                if current_time - self._last_save_time >= 1.0:
                    ts = now.strftime("%Y%m%d_%H%M%S")
                    save_path = self._capture_dir / f"frame_{ts}_{self._frame_id}.jpg"
                    cv2.imwrite(str(save_path), frame)
                    logger.debug("Saved frame to %s", save_path)
                    self._last_save_time = current_time

                # Classify helmets for person detections
                helmet_results = {}
                helmet_confs = {}
                for det in detections:
                    if det.bbox.class_name == "person" and det.track_id is not None:
                        x1, y1 = int(max(0, det.bbox.x1)), int(max(0, det.bbox.y1))
                        x2, y2 = int(min(frame.shape[1], det.bbox.x2)), int(min(frame.shape[0], det.bbox.y2))
                        if x2 > x1 and y2 > y1:
                            head_crop = frame[y1:y2, x1:x2]
                            has_helmet, conf = self._helmet_classifier.classify(head_crop)
                            helmet_results[det.track_id] = has_helmet
                            helmet_confs[det.track_id] = conf

                # Build rule context
                context = {
                    "has_helmet": helmet_results,
                    "helmet_confidence": helmet_confs,
                    "signal_state": SignalState.UNKNOWN,
                }

                # Run rule engine
                violations = self._rule_engine.process_frame(frame_data, context)

                for v in violations:
                    logger.info(
                        "VIOLATION DETECTED: %s (conf=%.2f, frames=%d)",
                        v.violation_type.value, v.confidence,
                        v.consecutive_frame_count,
                    )

                self._frame_id += 1

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self._camera.close()
            self._gps.stop()
            self._db.close()
            logger.info("Traffic-eye stopped (processed %d frames)", self._frame_id)

    def stop(self) -> None:
        """Signal the main loop to stop."""
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="Traffic-Eye Violation Detection System")
    parser.add_argument("--config", default="config", help="Path to config directory")
    parser.add_argument("--video", help="Path to video file for playback mode")
    parser.add_argument("--mock", action="store_true", help="Force mock mode for all components")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Override platform if mock flag set
    if args.mock:
        # Create a new config with mock platform
        config = AppConfig(
            camera=config.camera,
            detection=config.detection,
            helmet=config.helmet,
            ocr=config.ocr,
            violations=config.violations,
            gps=config.gps,
            reporting=config.reporting,
            cloud=config.cloud,
            storage=config.storage,
            thermal=config.thermal,
            logging=config.logging,
            platform="mock",
        )

    # Setup logging
    setup_logging(
        log_dir=config.logging.log_dir,
        level=config.logging.level,
        json_format=config.logging.json_format,
    )

    logger.info("Traffic-Eye starting (platform=%s)", config.platform)

    app = TrafficEyeApp(config, video_file=args.video)

    # Handle SIGTERM gracefully
    def handle_signal(signum, frame):
        logger.info("Received signal %d, stopping", signum)
        app.stop()

    signal.signal(signal.SIGTERM, handle_signal)

    app.run()


if __name__ == "__main__":
    main()
