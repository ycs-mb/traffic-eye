# tests/

Pytest test suite for Traffic-Eye. Tests use mock implementations exclusively and do not require any hardware or ML models.

## Structure

```
tests/
├── conftest.py                    # Shared pytest fixtures
├── test_models.py                 # Core data model tests
├── test_config.py                 # Configuration loading tests
├── test_database.py               # SQLite database tests
├── test_capture/
│   ├── test_camera.py             # Camera implementations
│   ├── test_buffer.py             # Circular frame buffer
│   └── test_gps.py                # GPS reader implementations
├── test_detection/
│   ├── test_tracker.py            # IoU tracker
│   └── test_signal.py             # Traffic signal HSV classifier
├── test_violation/
│   ├── test_temporal.py           # Temporal consistency checker
│   └── test_confidence.py         # Confidence aggregation
├── test_ocr/
│   └── test_validators.py         # Indian plate validation
├── test_reporting/                # Report generation tests
├── test_cloud/                    # Cloud verification tests
└── test_utils/
    ├── test_thermal.py            # Temperature monitoring
    └── test_logging.py            # Logging configuration
```

## Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src --cov-report=term-missing

# Run a specific test module
pytest tests/test_detection/test_tracker.py

# Run a specific test
pytest tests/test_violation/test_temporal.py::test_consecutive_frames

# Run tests matching a pattern
pytest -k "test_helmet"
```

## Test Configuration

Defined in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

## Key Test Areas

### test_models.py
- BoundingBox IoU computation
- Detection, GPSReading, FrameData creation
- ViolationType and SignalState enum values
- EvidencePacket hash storage

### test_config.py
- YAML config loading
- Default value handling
- Platform detection logic
- Invalid config error handling

### test_database.py
- Table creation and schema
- CRUD operations on all tables
- WAL mode verification
- Thread safety
- Foreign key cascading

### test_capture/
- MockCamera frame generation
- VideoFileCamera (with test fixtures)
- CircularFrameBuffer push/get/overflow
- MockGPS reading sequences
- NMEA sentence parsing

### test_detection/
- IOUTracker assignment and persistence
- Track creation for new detections
- Stale track removal
- TrafficSignalClassifier HSV detection
- Red/yellow/green classification accuracy

### test_violation/
- TemporalConsistencyChecker counter behavior
- Reset on condition failure
- Consecutive frame threshold
- ConfidenceAggregator weighted scoring
- OCR weight redistribution
- Threshold routing (local vs cloud vs discard)

### test_ocr/
- Indian plate format validation
- OCR error correction (digit<->letter swaps)
- State code extraction
- Edge cases (short strings, invalid formats)

### test_utils/
- MockThermalMonitor throttle/pause logic
- Temperature threshold behavior
- Logging setup and JSON format
- Log rotation

## Writing New Tests

1. Place tests in the appropriate subdirectory
2. Use fixtures from `conftest.py` for common setup
3. Use mock implementations (MockCamera, MockDetector, etc.) instead of real hardware
4. Name test files `test_*.py` and test functions `test_*`

Example:
```python
import numpy as np
from src.detection.tracker import IOUTracker
from src.models import BoundingBox, Detection
from datetime import datetime, timezone

def test_tracker_assigns_ids():
    tracker = IOUTracker()
    det = Detection(
        bbox=BoundingBox(x1=10, y1=10, x2=100, y2=100, confidence=0.9, class_name="car"),
        frame_id=0,
        timestamp=datetime.now(timezone.utc),
    )
    result = tracker.update([det])
    assert result[0].track_id == 1
```

## Deployment Testing on Raspberry Pi

```bash
cd /opt/traffic-eye
source venv/bin/activate

# Run tests (all use mocks, no hardware needed)
pytest

# Quick smoke test of the application
python -m src.main --mock --config config/settings_pi.yaml &
sleep 10
kill %1
```
