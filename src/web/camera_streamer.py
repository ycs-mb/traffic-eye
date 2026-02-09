#!/usr/bin/env python3
"""
Live camera streamer with YOLO detection for dashboard.
Captures from Pi Camera and runs real-time detection.
"""

import cv2
import numpy as np
import threading
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CameraStreamer:
    """Streams live camera feed with YOLO detection overlay."""

    def __init__(self, detector=None, helmet_classifier=None, camera_type="auto"):
        self.detector = detector
        self.helmet_classifier = helmet_classifier
        self.camera_type = camera_type  # "auto", "picamera", "usb"
        self.current_frame = None
        self.current_detections = []
        self.lock = threading.Lock()
        self.running = False
        self.camera = None
        self.thread = None
        self.fps = 0
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.last_frame_count = 0
        # Metrics tracking
        self.yolo_inference_time = 0
        self.helmet_inference_time = 0
        self.debug_mode = False

    def _init_camera(self):
        """Initialize Pi Camera or fallback to USB camera based on camera_type."""
        try:
            # Force USB camera if camera_type is "usb"
            if self.camera_type == "usb":
                logger.info("Camera type set to 'usb', skipping Pi Camera detection")
                return self._init_usb_camera()

            # Try Picamera2 first (modern Pi Camera) if not forced to USB
            if self.camera_type in ("auto", "picamera"):
                try:
                    from picamera2 import Picamera2

                    logger.info("Initializing Pi Camera with Picamera2...")
                    self.camera = Picamera2()

                    # Configure for video
                    config = self.camera.create_video_configuration(
                        main={"size": (640, 480), "format": "RGB888"},
                        controls={"FrameRate": 15}
                    )
                    self.camera.configure(config)
                    self.camera.start()

                    logger.info("✅ Pi Camera initialized successfully")
                    return True

                except ImportError:
                    logger.info("Picamera2 not available, trying legacy PiCamera...")
                    # Try legacy picamera
                    try:
                        from picamera import PiCamera
                        from picamera.array import PiRGBArray

                        logger.info("Initializing Pi Camera (legacy)...")
                        self.camera = PiCamera()
                        self.camera.resolution = (640, 480)
                        self.camera.framerate = 15
                        time.sleep(2)  # Camera warm-up

                        logger.info("✅ Pi Camera (legacy) initialized successfully")
                        return True

                    except ImportError:
                        logger.info("Legacy PiCamera not available, falling back to USB")

                except Exception as e:
                    logger.warning(f"Pi Camera initialization failed: {e}, falling back to USB")

            # Fallback to USB camera
            return self._init_usb_camera()

        except Exception as e:
            logger.error(f"Camera initialization failed: {e}")
            return False

    def _init_usb_camera(self):
        """Initialize USB camera with device detection."""
        logger.info("Initializing USB camera...")
        # Try device 1 first (common for USB webcams on Pi), then device 0
        for device_id in [1, 0]:
            logger.info(f"  Attempting /dev/video{device_id}...")
            self.camera = cv2.VideoCapture(device_id)

            if self.camera.isOpened():
                # Set to 720p for full FOV
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.camera.set(cv2.CAP_PROP_FPS, 30)
                self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))  # Use MJPEG for 30fps

                # Verify resolution
                actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fps = int(self.camera.get(cv2.CAP_PROP_FPS))

                logger.info(f"✅ USB camera initialized on /dev/video{device_id}")
                logger.info(f"   Resolution: {actual_width}x{actual_height} @ {actual_fps} FPS")
                return True
            else:
                logger.warning(f"  /dev/video{device_id} not available")

        logger.error("❌ Could not open any USB camera device")
        return False

    def _capture_frame_picamera2(self):
        """Capture frame from Picamera2."""
        try:
            # Capture array (already RGB)
            frame = self.camera.capture_array()
            # Convert RGB to BGR for OpenCV
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(f"Picamera2 capture error: {e}")
            return None

    def _capture_frame_legacy(self):
        """Capture frame from legacy PiCamera."""
        try:
            from picamera.array import PiRGBArray

            raw_capture = PiRGBArray(self.camera, size=(640, 480))
            self.camera.capture(raw_capture, format="bgr")
            frame = raw_capture.array
            raw_capture.truncate(0)
            return frame
        except Exception as e:
            logger.error(f"Legacy PiCamera capture error: {e}")
            return None

    def _capture_frame_usb(self):
        """Capture frame from USB camera."""
        ret, frame = self.camera.read()
        return frame if ret else None

    def capture_frame(self):
        """Capture a frame from the camera (auto-detect camera type)."""
        if self.camera is None:
            return None

        # Detect camera type and capture
        camera_type = type(self.camera).__name__

        if camera_type == 'Picamera2':
            return self._capture_frame_picamera2()
        elif camera_type == 'PiCamera':
            return self._capture_frame_legacy()
        else:  # VideoCapture (USB)
            return self._capture_frame_usb()

    def _detection_loop(self):
        """Main detection loop running in background thread."""
        logger.info("Starting camera detection loop...")

        while self.running:
            try:
                # Capture frame
                frame = self.capture_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                # Run detection if detector is available
                detections = []
                yolo_time = 0
                helmet_time = 0

                if self.detector and self.detector.is_loaded():
                    # Measure YOLO inference time
                    yolo_start = time.time()
                    detection_objs = self.detector.detect(frame, self.frame_count)
                    yolo_time = (time.time() - yolo_start) * 1000  # Convert to ms

                    # Convert Detection objects to dict format
                    for det in detection_objs:
                        det_dict = {
                            'x1': det.bbox.x1,
                            'y1': det.bbox.y1,
                            'x2': det.bbox.x2,
                            'y2': det.bbox.y2,
                            'class_name': det.bbox.class_name,
                            'confidence': det.bbox.confidence,
                            'track_id': getattr(det, 'track_id', None)
                        }

                        # Add helmet detection for persons on motorcycles
                        if det.bbox.class_name == 'person' and self.helmet_classifier:
                            # Extract head region (top 30% of bbox)
                            x1, y1 = int(det.bbox.x1), int(det.bbox.y1)
                            x2, y2 = int(det.bbox.x2), int(det.bbox.y2)
                            head_height = int((y2 - y1) * 0.3)
                            head_y2 = y1 + head_height

                            if head_y2 > y1 and x2 > x1:
                                head_crop = frame[y1:head_y2, x1:x2]
                                if head_crop.size > 0:
                                    # Measure helmet classifier time
                                    helmet_start = time.time()
                                    has_helmet, helmet_conf = self.helmet_classifier.classify(head_crop)
                                    helmet_time += (time.time() - helmet_start) * 1000  # Convert to ms

                                    det_dict['has_helmet'] = has_helmet
                                    det_dict['helmet_confidence'] = helmet_conf

                        detections.append(det_dict)

                # Store inference times
                if yolo_time > 0:
                    self.yolo_inference_time = yolo_time
                if helmet_time > 0:
                    self.helmet_inference_time = helmet_time

                # Update shared state
                with self.lock:
                    self.current_frame = frame.copy()
                    self.current_detections = detections
                    self.frame_count += 1

                # Calculate FPS (frames per second)
                current_time = time.time()
                if current_time - self.last_fps_time >= 1.0:
                    frames_in_last_second = self.frame_count - self.last_frame_count
                    self.fps = frames_in_last_second
                    self.last_frame_count = self.frame_count
                    self.last_fps_time = current_time

                # Limit to ~15 FPS
                time.sleep(0.066)

            except Exception as e:
                logger.error(f"Detection loop error: {e}", exc_info=True)
                time.sleep(0.5)

        logger.info("Detection loop stopped")

    def start(self):
        """Start the camera streamer."""
        if self.running:
            return

        # Initialize camera
        if not self._init_camera():
            logger.error("Failed to initialize camera")
            return

        # Start detection thread
        self.running = True
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        logger.info("Camera streamer started")

    def stop(self):
        """Stop the camera streamer."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

        # Release camera
        if self.camera:
            try:
                camera_type = type(self.camera).__name__
                if camera_type == 'Picamera2':
                    self.camera.stop()
                elif camera_type == 'PiCamera':
                    self.camera.close()
                else:  # VideoCapture
                    self.camera.release()
            except Exception as e:
                logger.error(f"Error releasing camera: {e}")

        logger.info("Camera streamer stopped")

    def get_frame_with_overlay(self):
        """Get the current frame with detection overlay."""
        with self.lock:
            if self.current_frame is None:
                # Return placeholder (720p)
                placeholder = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(placeholder, "Initializing camera...", (400, 360),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
                return placeholder

            frame = self.current_frame.copy()
            detections = self.current_detections.copy()

        # Draw detections
        for idx, det in enumerate(detections):
            x1, y1, x2, y2 = int(det['x1']), int(det['y1']), int(det['x2']), int(det['y2'])
            class_name = det.get('class_name', 'unknown')
            confidence = det.get('confidence', 0.0)
            track_id = det.get('track_id', None)

            # Color coding
            colors = {
                'person': (0, 255, 0),      # Green
                'motorcycle': (255, 165, 0), # Orange
                'car': (0, 165, 255),       # Light blue
                'truck': (255, 0, 255),     # Magenta
                'bus': (255, 255, 0),       # Yellow
                'bicycle': (0, 255, 255),   # Cyan
                'traffic light': (255, 0, 0) # Red
            }
            color = colors.get(class_name, (255, 255, 255))

            # Draw bounding box (thicker in debug mode)
            box_thickness = 3 if self.debug_mode else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, box_thickness)

            # Prepare label
            if self.debug_mode:
                # Debug mode: show ID, confidence, and helmet
                label_parts = [f"ID:{track_id or idx}"]
                label_parts.append(f"{class_name}")
                label_parts.append(f"{confidence:.3f}")
                if 'has_helmet' in det:
                    helmet_status = "✓H" if det['has_helmet'] else "✗H"
                    label_parts.append(helmet_status)
                label = " | ".join(label_parts)
            else:
                # Normal mode: simple label
                label = f"{class_name} {confidence:.2f}"
                if 'has_helmet' in det:
                    helmet_status = "HELMET" if det['has_helmet'] else "NO HELMET"
                    label += f" | {helmet_status}"

            # Draw label background
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(frame, (x1, y1 - label_h - 10),
                         (x1 + label_w, y1), color, -1)

            # Draw label text
            cv2.putText(frame, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            # Debug mode: Draw confidence bar
            if self.debug_mode:
                bar_width = int((x2 - x1) * confidence)
                cv2.rectangle(frame, (x1, y2 + 2), (x1 + bar_width, y2 + 8), color, -1)

        # Add overlays
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        det_count = f"Detections: {len(detections)} | FPS: {self.fps}"
        cv2.putText(frame, det_count, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Debug mode: Show frame number and inference times
        if self.debug_mode:
            debug_info = f"Frame: #{self.frame_count}"
            cv2.putText(frame, debug_info, (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            if self.yolo_inference_time > 0:
                yolo_info = f"YOLO: {self.yolo_inference_time:.1f}ms"
                cv2.putText(frame, yolo_info, (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            if self.helmet_inference_time > 0:
                helmet_info = f"Helmet: {self.helmet_inference_time:.1f}ms"
                cv2.putText(frame, helmet_info, (10, 150),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        return frame
