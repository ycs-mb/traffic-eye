# Traffic-Eye

Edge-AI traffic violation detection system designed for Raspberry Pi deployment. Detects helmet violations, red light jumping, and wrong-side driving using on-device ML inference with optional cloud verification.

## Architecture

```
Camera/Video -> Detection (YOLOv8n) -> Helmet/Signal Classification
     |                                        |
     v                                        v
Frame Buffer -----> Rule Engine -----> Temporal Consistency
                        |                     |
                        v                     v
                  Evidence Packager --> Confidence Routing
                        |               /           \
                        v           >= 0.96       0.70-0.96
                   SQLite DB     Local Report    Cloud Verify
                        |              |              |
                        v              v              v
                   Email Queue    Email Send    GPT-4V / Gemini
```

## Violation Types

| Type | Method | Min Frames |
|------|--------|-----------|
| No Helmet | YOLOv8n person+motorcycle detection + MobileNetV3 helmet classifier | 3 |
| Red Light Jump | Traffic signal HSV color detection + vehicle position heuristic | 5 |
| Wrong Side | GPS heading deviation from expected road bearing | 3s duration |

## Hardware Requirements

- Raspberry Pi 4 (4GB or 8GB RAM)
- Pi Camera Module v2 (or USB camera)
- NEO-6M GPS module (UART, optional)
- 64GB MicroSD card (A2 class recommended)
- 10000mAh power bank (for mobile deployment)

Estimated BOM: ~4,000 INR

## Quick Start

### On Raspberry Pi

```bash
# Clone the repository
git clone <repo-url> /tmp/traffic-eye
cd /tmp/traffic-eye

# Run the automated setup script (installs dependencies, creates directories, configures systemd)
sudo bash scripts/setup.sh

# Activate the virtual environment
source /opt/traffic-eye/venv/bin/activate
cd /opt/traffic-eye

# Run in mock mode (no hardware needed)
python -m src.main --mock

# Run with Pi camera
python -m src.main --config config/settings_pi.yaml

# Run with a video file
python -m src.main --video path/to/traffic_footage.mp4
```

### On macOS / Linux (Development)

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run in mock mode
python -m src.main --mock

# Run with webcam
python -m src.main

# Run tests
pytest
```

## CLI Options

```
python -m src.main [OPTIONS]

  --config DIR    Path to config directory (default: "config")
  --video FILE    Path to video file for playback mode
  --mock          Force mock mode for all hardware components
```

## Documentation

Complete documentation is available in the `docs/` directory:

### **Field Testing & Deployment**
- **[Field Deployment Guide](docs/field-testing/FIELD_DEPLOYMENT_COMPLETE.md)** - Complete guide for field testing setup
- **[Quick Reference](docs/field-testing/FIELD_QUICK_REFERENCE.md)** - Printable quick reference card (keep in car)
- **[Testing Checklist](docs/field-testing/FIELD_TESTING_CHECKLIST.md)** - Pre-flight and troubleshooting checklist
- **[Installation Guide](docs/field-testing/INSTALL_FIELD_TESTING.txt)** - Quick start installation summary
- **[Architecture](docs/field-testing/DEPLOYMENT_ARCHITECTURE.md)** - System architecture diagrams

### **Development & History**
- **[Archive](docs/archive/)** - Historical documentation (setup, testing, reports, planning)

**Quick Start**: Read `docs/field-testing/INSTALL_FIELD_TESTING.txt` for field deployment instructions.

## Project Structure

```
raspi-traffic-observer/
├── config/             # YAML configuration and email templates
├── data/               # Runtime data (evidence, logs, queue)
├── models/             # TFLite model files (not in repo)
├── scripts/            # Setup and utility scripts
├── src/                # Application source code
│   ├── capture/        # Camera and GPS input
│   ├── cloud/          # Cloud verification (Gemini/GPT-4V)
│   ├── detection/      # Object detection, helmet classifier, tracker
│   ├── ocr/            # License plate OCR and validation
│   ├── reporting/      # Evidence packaging, reports, email sender
│   ├── utils/          # Database, logging, thermal, storage
│   ├── config.py       # Configuration dataclasses and loader
│   ├── main.py         # Application entry point and orchestrator
│   ├── models.py       # Core data models (Detection, Violation, etc.)
│   └── platform_factory.py  # Platform-aware component creation
├── systemd/            # systemd service and timer files
├── tests/              # pytest test suite
└── pyproject.toml      # Build config and dependencies
```

Each folder contains its own `README.md` with detailed documentation.

## Configuration

All configuration lives in `config/settings.yaml`. Key sections:

- **camera**: Resolution, FPS, frame sampling rate
- **detection**: Model path, confidence threshold, target classes
- **helmet**: Helmet classifier model and threshold
- **violations**: Cooldown between reports, hourly rate limit
- **gps**: Enable/disable, speed gate
- **reporting**: Evidence directory, email SMTP settings
- **cloud**: Provider (gemini/openai), API key, confidence threshold
- **thermal**: Throttle and pause temperatures
- **storage**: Disk usage limit, retention policies

See `config/README.md` for full configuration reference.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `TRAFFIC_EYE_EMAIL_PASSWORD` | SMTP password for email reports |
| `TRAFFIC_EYE_CLOUD_API_KEY` | API key for Gemini or OpenAI cloud verification |

## Deployment on Raspberry Pi

### Automated Setup

```bash
sudo bash scripts/setup.sh
```

This script:
1. Installs system packages (python3, picamera2, ffmpeg, gpsd)
2. Creates `/opt/traffic-eye` (code) and `/var/lib/traffic-eye` (data)
3. Sets up a Python virtual environment with `--system-site-packages`
4. Installs all Python dependencies
5. Copies project files and generates Pi-specific config
6. Installs systemd services
7. Enables the camera interface and allocates 128MB GPU memory

### Running as a Service

```bash
# Enable and start the main detection service
sudo systemctl enable traffic-eye
sudo systemctl start traffic-eye

# Enable the email/cloud sender timer (runs every 5 minutes)
sudo systemctl enable traffic-eye-sender.timer
sudo systemctl start traffic-eye-sender.timer

# Check status
sudo systemctl status traffic-eye
sudo journalctl -u traffic-eye -f
```

### GPS Setup

If using a NEO-6M GPS module via UART:

```bash
# Enable serial port
sudo raspi-config  # Interface Options -> Serial Port -> No login shell, Yes hardware

# Configure gpsd
sudo systemctl enable gpsd
sudo systemctl start gpsd

# Test GPS
cgps -s
```

Then set `gps.enabled: true` in your config.

## Performance

| Metric | Value |
|--------|-------|
| Effective FPS | 4-6 fps (YOLOv8n INT8 on Pi 4) |
| Memory usage | ~300MB base + ~150MB frame buffer |
| Battery life | 3-4 hours (full load), 6+ hours (duty cycling) |
| Thermal throttle | 75C (skip extra frames), 80C (30s pause) |

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=term-missing

# Specific module
pytest tests/test_detection/
```

## Technology Stack

- **Python 3.11**
- **OpenCV** (headless) - image processing
- **TFLite Runtime** - edge ML inference
- **NumPy / Pillow** - array and image handling
- **Picamera2** - Pi camera control
- **gps3** - GPS via gpsd
- **SQLite** (WAL mode) - crash-safe database
- **Jinja2** - email templates
- **httpx** - cloud API calls
- **psutil** - system monitoring
- **systemd** - service management
# traffic-eye
