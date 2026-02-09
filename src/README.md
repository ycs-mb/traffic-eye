# src/

Main application source code for Traffic-Eye. This package is structured as a modular pipeline with platform-agnostic abstractions.

## Module Overview

| Module | Purpose |
|--------|---------|
| `main.py` | Application entry point and `TrafficEyeApp` orchestrator |
| `config.py` | Frozen dataclass configuration with YAML loader |
| `models.py` | Core data models shared across all modules |
| `platform_factory.py` | Factory functions for platform-specific component creation |

## Subpackages

| Package | Purpose |
|---------|---------|
| `capture/` | Camera input (Pi, OpenCV, video file, mock) and GPS readers |
| `detection/` | Object detection (YOLOv8n), helmet classification, signal detection, tracking |
| `violation/` | Rule engine, temporal consistency, confidence aggregation |
| `ocr/` | License plate text extraction and Indian plate format validation |
| `reporting/` | Evidence packaging, report generation, email sending |
| `cloud/` | Cloud verification queue and API clients (Gemini, GPT-4V) |
| `utils/` | Database, logging, thermal monitoring, storage management |

## main.py - TrafficEyeApp

The `TrafficEyeApp` class orchestrates the full detection pipeline:

1. Creates all components via `platform_factory` based on detected/configured platform
2. Opens camera and GPS
3. Runs the main loop:
   - Reads frames, applies Nth-frame sampling
   - Checks thermal state (throttle/pause if too hot)
   - Runs YOLOv8n object detection
   - Tracks objects across frames with IoU tracker
   - Classifies helmets on detected persons
   - Evaluates violation rules
   - Logs confirmed violations
4. Handles SIGTERM for graceful shutdown

### CLI Entry Point

```bash
python -m src.main [--config DIR] [--video FILE] [--mock]
```

- `--config`: Path to config directory containing `settings.yaml` (default: `"config"`)
- `--video`: Video file path for playback mode (replaces live camera)
- `--mock`: Forces all components to use mock implementations (no hardware needed)

## config.py - Configuration

All configuration is defined as frozen (immutable) dataclasses:

- `CameraConfig` - resolution, fps, frame sampling, buffer size
- `DetectionConfig` - model path, thresholds, thread count, target classes
- `HelmetConfig` - classifier model path and threshold
- `OCRConfig` - OCR engine and confidence threshold
- `ViolationsConfig` - cooldown and rate limiting
- `GPSConfig` - enable/disable, speed gate
- `EmailConfig` - SMTP settings (password from env var)
- `ReportingConfig` - evidence paths, clip settings, email config
- `CloudConfig` - provider, API key (from env var), thresholds
- `StorageConfig` - disk usage limits and retention
- `ThermalConfig` - throttle/pause temperatures
- `LoggingConfig` - level, format, log directory
- `AppConfig` - root config combining all above

Key functions:
- `load_config(config_dir)` - Loads `settings.yaml` and returns a frozen `AppConfig`
- `detect_platform()` - Auto-detects platform: `"pi"`, `"macos"`, `"linux"`, or `"unknown"`
- `resolve_platform(config)` - Resolves `"auto"` platform to actual platform string

## models.py - Data Models

Shared data models used across the pipeline:

- `ViolationType` (enum) - `NO_HELMET`, `RED_LIGHT_JUMP`, `WRONG_SIDE`
- `SignalState` (enum) - `RED`, `YELLOW`, `GREEN`, `UNKNOWN`
- `BoundingBox` - Detection box with confidence, class name, IoU computation
- `Detection` - Bounding box + frame ID + timestamp + optional track ID
- `GPSReading` - Latitude, longitude, altitude, speed, heading, fix quality
- `FrameData` - Frame array + detections + GPS + metadata
- `ViolationCandidate` - Violation type, confidence, evidence frames, plate text
- `EvidencePacket` - Complete evidence: JPEG frames, video clip path, SHA256 hashes

## platform_factory.py - Component Creation

Factory functions that return the appropriate implementation based on the configured platform:

| Function | Pi | macOS/Linux | Mock |
|----------|-----|-------------|------|
| `create_camera()` | `PiCamera` (picamera2) | `OpenCVCamera` (V4L2/webcam) | `MockCamera` |
| `create_gps()` | `GpsdGPS` (gpsd daemon) | `MockGPS` | `MockGPS` |
| `create_detector()` | `TFLiteDetector` (YOLOv8n) | `TFLiteDetector` (fallback: mock) | `MockDetector` |
| `create_helmet_classifier()` | `TFLiteHelmetClassifier` | `TFLiteHelmetClassifier` (fallback: mock) | `MockHelmetClassifier` |
| `create_thermal_monitor()` | `VcgencmdThermalMonitor` | `PsutilThermalMonitor` | `MockThermalMonitor` |

All factories gracefully fall back to mock implementations if hardware-specific packages are unavailable.

## Deployment on Raspberry Pi

The application is designed to run as a systemd service. On Pi, it uses:
- `picamera2` for camera access (pre-installed on Pi OS)
- `tflite-runtime` for efficient INT8 model inference
- `gps3` for GPS data via the `gpsd` daemon
- `vcgencmd` for accurate SoC temperature readings

See `scripts/README.md` for automated deployment and `systemd/README.md` for service configuration.
