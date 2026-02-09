# src/utils/

Utility modules: database, logging, thermal monitoring, and storage management.

## Files

| File | Purpose |
|------|---------|
| `database.py` | Thread-safe SQLite database with WAL mode |
| `logging_config.py` | Structured logging setup with rotation |
| `thermal.py` | CPU temperature monitoring (Pi, cross-platform, mock) |
| `storage.py` | Disk usage monitoring and automatic cleanup |

## database.py - SQLite Database

Thread-safe SQLite wrapper using WAL (Write-Ahead Logging) mode for crash-safe writes.

### Schema

Four tables:

**violations** - Core violation records
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | UUID |
| type | TEXT | Violation type (no_helmet, red_light_jump, wrong_side) |
| confidence | REAL | Aggregated confidence score |
| plate_text | TEXT | Detected license plate (nullable) |
| gps_lat, gps_lon | REAL | GPS coordinates (nullable) |
| gps_heading, gps_speed_kmh | REAL | GPS data (nullable) |
| timestamp | TEXT | ISO 8601 timestamp |
| status | TEXT | pending, processing, verified, sent, discarded, cleaned |
| consecutive_frames | INTEGER | Number of consecutive frames detected |

**evidence_files** - Associated media files
| Column | Type | Description |
|--------|------|-------------|
| violation_id | TEXT (FK) | References violations.id |
| file_path | TEXT | Absolute path to evidence file |
| file_type | TEXT | "frame" or "video" |
| file_hash | TEXT | SHA256 hash for integrity |

**cloud_queue** - Pending cloud verification requests
| Column | Type | Description |
|--------|------|-------------|
| violation_id | TEXT (FK) | References violations.id |
| status | TEXT | pending, done, failed |
| attempts | INTEGER | Retry count |
| response_json | TEXT | Cloud API response |

**email_queue** - Pending email sends
| Column | Type | Description |
|--------|------|-------------|
| violation_id | TEXT (FK) | References violations.id |
| status | TEXT | pending, processing, sent, failed |
| attempts | INTEGER | Retry count |

### Key Features

- **WAL mode**: Readers don't block writers; crash-safe
- **Thread-safe**: All operations use a threading lock
- **Transaction context manager**: `with db.transaction() as cursor:`
- **Foreign keys enabled**: CASCADE deletes on violations
- **Indexed**: status and timestamp columns for fast queries

### Usage

```python
db = Database("/var/lib/traffic-eye/traffic_eye.db")
db.insert_violation(violation_id="...", violation_type="no_helmet", confidence=0.92, ...)
db.enqueue_email(violation_id)
pending = db.get_pending_emails(limit=20)
db.close()
```

## logging_config.py - Logging

Configures application-wide logging with console and rotating file handlers.

### Setup

```python
from src.utils.logging_config import setup_logging
setup_logging(log_dir="data/logs", level="INFO", json_format=False)
```

### Outputs

- **Console**: Human-readable format: `2024-01-15 10:30:00 | INFO     | src.main | Starting...`
- **File**: Rotating log file at `data/logs/traffic-eye.log`
  - Max size: 10MB per file
  - Keeps 5 backup files
  - Supports JSON format for log aggregation tools

### JSON Format

When `json_format: true`, log lines are JSON objects:
```json
{"timestamp": "2024-01-15T10:30:00", "level": "INFO", "logger": "src.main", "message": "Starting..."}
```

### Suppressed Loggers

Third-party libraries are set to WARNING level to reduce noise: `urllib3`, `httpx`, `PIL`.

## thermal.py - Temperature Monitoring

Monitors CPU temperature and controls processing rate to prevent overheating.

### Implementations

| Class | Platform | Method |
|-------|----------|--------|
| `VcgencmdThermalMonitor` | Raspberry Pi | `vcgencmd measure_temp` (most accurate on Pi). Falls back to `/sys/class/thermal/thermal_zone0/temp`. |
| `PsutilThermalMonitor` | Linux, macOS | `psutil.sensors_temperatures()`. Falls back to 50C default if sensors unavailable. |
| `MockThermalMonitor` | Testing | Returns configurable temperature. |

### Throttle Behavior

The main loop in `TrafficEyeApp` checks temperature every frame:

| Temperature | Action |
|-------------|--------|
| < 75C | Normal operation |
| 75C - 80C | **Throttle**: Skip 2x frames (halve effective FPS) |
| >= 80C | **Pause**: Stop processing for 30 seconds |

### Usage

```python
monitor = VcgencmdThermalMonitor()
temp = monitor.get_cpu_temp()       # e.g., 62.5
monitor.should_throttle(75.0)       # False
monitor.should_pause(80.0)          # False
```

### Raspberry Pi Thermal Notes

- Pi 4 throttles its own CPU at 80C (firmware level)
- Traffic-Eye preemptively throttles at 75C and pauses at 80C
- In enclosed cases (e.g., helmet mount), temperatures can reach 70C+ in Indian summer
- Adding a heatsink and small fan is recommended for sustained operation

## storage.py - Storage Management

`StorageManager` monitors disk usage and enforces retention policies.

### Cleanup Logic

```
check_and_cleanup()
    |
    +--> Delete evidence older than retention_days (30 days default)
    |
    +--> If disk usage > max_usage_percent (80%):
    |       Delete discarded violation evidence
    |
    +--> If still over threshold:
    |       Delete oldest completed/sent violations
    |
    +--> Remove orphaned evidence directories (no DB record)
```

### Deletion Priority

1. Expired evidence (> 30 days old, non-pending)
2. Discarded violation evidence (cloud verification rejected)
3. Oldest sent/completed violations (already reported)
4. Never deletes pending or in-progress violations

### Usage

```python
manager = StorageManager(config, db)
usage = manager.get_usage_percent()     # e.g., 72.3
freed = manager.check_and_cleanup()     # bytes freed
```

## Deployment on Raspberry Pi

- Database file lives at `/var/lib/traffic-eye/traffic_eye.db`
- Logs at `/var/lib/traffic-eye/logs/traffic-eye.log`
- Evidence at `/var/lib/traffic-eye/evidence/`
- The systemd service has `ReadWritePaths=/var/lib/traffic-eye` for write access
- WAL mode ensures the database survives unexpected power loss
- Use A2-class MicroSD cards for better random I/O performance
