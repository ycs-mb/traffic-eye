# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Traffic-Eye is an edge-AI traffic violation detection system for Raspberry Pi that detects helmet violations, red light jumping, and wrong-side driving using on-device ML inference with optional cloud verification. The system runs real-time YOLO object detection with a helmet classifier and uses Gemini API for license plate OCR.

**Target Platform**: Raspberry Pi 4 (4GB+ RAM, ARM64)
**Camera**: USB Webcam (SNAP U2) via /dev/video1
**Tailscale IP**: 100.107.114.5
**Dashboard URL**: http://100.107.114.5:8080

## Development Commands

### Running the Application

```bash
# Development mode (mock hardware)
source venv/bin/activate
python -m src.main --mock

# With video file
python -m src.main --video path/to/video.mp4

# With real Pi Camera (on Raspberry Pi)
python -m src.main

# Live dashboard with camera feed
python src/web/dashboard_camera.py
```

### Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=term-missing

# Integration tests only
python scripts/test_integration.py

# Test live dashboard with demo frames
python scripts/test_live_dashboard.py
```

### Model Training & Conversion

```bash
# Train helmet classifier
python scripts/train_helmet.py

# Convert to TFLite with Float16 quantization
python scripts/convert_float16.py

# Export YOLOv8 to TFLite
python scripts/export_yolov8n_tflite.py
```

### Field Testing Deployment

```bash
# Complete field testing setup (one command)
bash scripts/deploy_field_testing.sh

# Setup auto-start on boot
bash scripts/setup_autostart.sh

# Check power health (undervoltage, throttling)
bash scripts/check_power.sh

# Test camera
bash scripts/setup_camera.sh

# Test GPS
bash scripts/setup_gps.sh
```

### Systemd Services

```bash
# Dashboard (live camera feed with YOLO overlay)
sudo systemctl enable traffic-eye-dashboard
sudo systemctl start traffic-eye-dashboard
sudo journalctl -u traffic-eye-dashboard -f

# Main detection service (for production)
sudo systemctl enable traffic-eye-field
sudo systemctl start traffic-eye-field
sudo journalctl -u traffic-eye-field -f
```

## Critical Architecture Patterns

### Platform Factory Pattern

The system uses `platform_factory.py` to create platform-specific implementations. This is the **only** place where platform detection happens:

- **Mock mode**: All components return mock implementations (no hardware)
- **Pi mode**: Uses Picamera2, GPSD, TFLite on ARM
- **Desktop mode**: Uses OpenCV camera, mock GPS, TFLite on x86

**Never** import platform-specific modules directly (e.g., `from picamera2 import Picamera2`). Always use the factory functions:
- `create_camera(config, video_file=None)`
- `create_gps(config)`
- `create_detector(config)`
- `create_helmet_classifier(config)`
- `create_thermal_monitor(config)`

### Detection Pipeline Flow

```
Camera → Frame Buffer → YOLOv8n → Helmet Classifier → Tracker → Rule Engine → Violation
                                         ↓
                              Temporal Consistency (3-5 frames)
                                         ↓
                              Confidence Routing (0.7-0.96 threshold)
                                         ↓
                              Evidence Packager → SQLite + Email Queue
```

**Key Files**:
- `src/main.py`: Orchestrates the entire pipeline
- `src/detection/detector.py`: YOLOv8n TFLite inference
- `src/detection/helmet.py`: MobileNetV3 helmet classifier
- `src/detection/tracker.py`: IOU-based object tracking
- `src/violation/rules.py`: Violation detection logic
- `src/violation/temporal.py`: Multi-frame consistency checks

### Model Specifications

**YOLOv8n Object Detector** (`models/yolov8n_int8.tflite`):
- INT8 quantized for Raspberry Pi
- Input: 320×320×3 or 640×640×3 (configurable)
- Detects: person, motorcycle, car, truck, bus, bicycle, traffic light
- Inference: ~150-200ms on Pi 4

**Helmet Classifier** (`models/helmet_cls_int8.tflite`):
- MobileNetV3-Small, Float16 quantized
- Input: 96×96×3 float32 [0-1]
- Output: sigmoid score (>0.5 = helmet detected)
- Inference: ~71ms on Pi 4
- Trained on synthetic data (needs real-world retraining)

**Critical**: INT8 quantization failed for helmet model due to hard-swish activation. Use Float16 instead.

### Configuration System

All config is in `config/settings.yaml` loaded as frozen dataclasses via `src/config.py`.

**Environment Variables** (set in `/etc/traffic-eye.env`):
- `TRAFFIC_EYE_CLOUD_API_KEY`: Gemini API key for cloud OCR
- `TRAFFIC_EYE_EMAIL_PASSWORD`: SMTP password for reports

**Important config sections**:
- `camera.process_every_nth_frame`: Controls detection FPS (5 = process every 5th frame)
- `detection.confidence_threshold`: YOLO confidence (0.5 default)
- `helmet.confidence_threshold`: Helmet detection threshold (0.85 default)
- `violations.cooldown_seconds`: Prevent duplicate reports (30s default)

### Live Dashboard Architecture

Two dashboard implementations:

1. **`src/web/dashboard_camera.py`** - Live Pi Camera feed with real-time YOLO detection overlay
   - Runs camera capture + detection in background thread
   - Streams MJPEG video via Flask on port 8080
   - **This is the production dashboard** (auto-starts on boot)

2. **`src/web/dashboard_live.py`** - Generic dashboard that receives frames via HTTP POST
   - Used for remote frame publishing from main detection loop
   - Deprecated in favor of dashboard_camera.py

**Camera Streamer** (`src/web/camera_streamer.py`):
- Handles Pi Camera (Picamera2), legacy PiCamera, and USB cameras
- Runs YOLOv8n + helmet classifier in real-time
- Draws color-coded bounding boxes (Green=Person, Orange=Motorcycle, etc.)
- Calculates FPS and adds overlays (timestamp, detection count)

### Detection Object Structure

Models are defined in `src/models.py`:

```python
@dataclass
class BoundingBox:
    x1, y1, x2, y2: float
    confidence: float
    class_name: str
    class_id: int

@dataclass
class Detection:
    bbox: BoundingBox
    frame_id: int
    timestamp: datetime
    track_id: Optional[int]  # Added by tracker

@dataclass
class ViolationCandidate:
    violation_type: ViolationType
    confidence: float
    frames: list[FrameData]
    plate_text: Optional[str]  # From Gemini OCR
    plate_confidence: float
    gps: Optional[GPSReading]
```

**Critical**: Detection objects have nested structure (`det.bbox.x1`, not `det.x1`). The dashboard expects either Detection objects or dicts with flat structure.

### Database Schema

SQLite database at `data/traffic_eye.db` with WAL mode for crash safety:

- **violations**: Main violation records with plate, GPS, confidence
- **evidence**: Links to image/video files for each violation
- **queue**: Email/cloud verification queue

Access via `src/utils/database.py` Database class.

## Common Issues & Solutions

### Camera Won't Initialize

**Current Camera**: USB Webcam (SNAP U2) connected via USB

Check camera with: `v4l2-ctl --list-devices`
If fails, verify:
- USB cable properly connected
- Camera shows up in `ls /dev/video*` (should be /dev/video1)
- User in `video` group: `groups` (should include 'video')
- Camera type in config: `camera.type: "usb"` in settings.yaml

**Troubleshooting**:
```bash
# Test USB camera manually
python scripts/test_webcam.py

# Check video devices
v4l2-ctl --list-devices

# Check if another process is using camera
ps aux | grep -E "(camera|video)"

# Restart camera service
sudo systemctl restart traffic-eye-dashboard

# Check logs
sudo journalctl -u traffic-eye-dashboard -f
```

### High CPU Usage / Thermal Throttling

Check with: `vcgencmd measure_temp` and `vcgencmd get_throttled`
- Normal temp: 50-70°C
- Throttling starts at 80°C
- Solutions:
  - Increase `camera.process_every_nth_frame` (lower FPS)
  - Add heatsink/fan
  - Lower `CPUQuota` in systemd service

### GPS Not Getting Fix

Requires clear sky view. Cold start takes 1-5 minutes.
Test with: `cgps` or `gpsmon`
Check device: `ls -l /dev/ttyUSB* /dev/ttyACM*`

### Models Not Loading

Models are included in repo (`models/*.tflite`). If missing:
- YOLOv8n: Download from Ultralytics or train with `scripts/export_yolov8n_tflite.py`
- Helmet: Train with `scripts/train_helmet.py` (requires real data)

### Dashboard Shows Placeholder

Dashboard at http://100.107.114.5:8080 should show live feed. If placeholder:
- Check camera streamer initialized: `ps aux | grep dashboard_camera`
- Check logs: `sudo journalctl -u traffic-eye-dashboard -f`
- Test camera manually: `python scripts/setup_camera.sh`

### Service Won't Auto-Start

Verify: `systemctl is-enabled traffic-eye-dashboard`
If disabled: `sudo systemctl enable traffic-eye-dashboard`
Test: `sudo reboot` then wait 60 seconds

## Code Style Notes

- Use frozen dataclasses for immutable config/models
- Logging via module-level `logger = logging.getLogger(__name__)`
- Type hints required (Python 3.11+)
- Hardware access **only** through platform_factory
- Frame processing at configured intervals (not every frame)
- Detection coordinates are **absolute pixels**, not normalized [0-1]

## Field Testing Workflow

1. Deploy with: `bash scripts/deploy_field_testing.sh`
2. Connect to Tailscale VPN on iPad
3. Access dashboard: http://100.107.114.5:8080
4. Dashboard auto-starts on boot (systemd service)
5. View real-time detections with color-coded bounding boxes
6. Monitor system metrics (CPU, temp, memory)

**Auto-start is configured**: After reboot, wait 60 seconds and access dashboard. No manual steps required.
