# data/

Runtime data directory for Traffic-Eye. Created automatically on first run. Contains evidence, logs, and offline queues.

## Structure

```
data/
├── evidence/          # Violation evidence files
│   └── <uuid>/        # One directory per violation
│       ├── frame_00.jpg
│       ├── frame_01.jpg
│       ├── frame_02.jpg
│       └── clip.mp4
├── queue/             # Offline queue storage
├── logs/              # Application log files
│   └── traffic-eye.log
├── captures/          # Periodic frame captures (1 per second)
│   └── frame_20240115_103000_42.jpg
└── traffic_eye.db     # SQLite database (WAL mode)
```

## evidence/

Violation evidence organized by violation UUID. Each directory contains:
- **frame_XX.jpg** - Best evidence frames with bounding box annotations and metadata overlay (up to 3 by default)
- **clip.mp4** - Video clip (2 seconds before to 3 seconds after the violation)

Files include SHA256 hashes stored in the database for integrity verification.

### Retention Policy

- Violation evidence: kept for 30 days (configurable via `storage.evidence_retention_days`)
- Discarded violations: cleaned up when disk usage exceeds threshold
- Auto-cleanup at 80% disk usage (configurable via `storage.max_usage_percent`)

## queue/

Offline queue directory for pending operations. The actual queue state is persisted in the SQLite database tables (`cloud_queue`, `email_queue`), so this directory serves as supplementary storage.

## logs/

Application log files with automatic rotation:
- **traffic-eye.log** - Current log file
- **traffic-eye.log.1** through **traffic-eye.log.5** - Rotated backups
- Max file size: 10MB
- Format: human-readable or JSON (configurable)

## captures/

Periodic frame captures saved at 1-second intervals for monitoring purposes. Files are named with timestamp and frame ID: `frame_YYYYMMDD_HHMMSS_<frame_id>.jpg`.

## traffic_eye.db

SQLite database in WAL (Write-Ahead Logging) mode. Contains four tables:
- `violations` - Detected violation records
- `evidence_files` - Associated evidence file paths and hashes
- `cloud_queue` - Pending cloud verification requests
- `email_queue` - Pending email sends

See `src/utils/README.md` for full schema documentation.

## Raspberry Pi Paths

On Pi deployment (after running `scripts/setup.sh`), data is stored at:

```
/var/lib/traffic-eye/
├── evidence/
├── queue/
├── logs/
├── captures/
└── traffic_eye.db
```

The systemd service has `ReadWritePaths=/var/lib/traffic-eye` to restrict write access to this directory only.

## Disk Space Considerations

At 720p with 3 frames + 1 video clip per violation:
- ~500KB per violation (3 JPEGs + short MP4)
- 20 violations/hour max = ~10MB/hour
- 30 days retention = ~7GB maximum

Periodic captures (1 per second) are not retained long-term and should be cleaned up or disabled in production.

Use an A2-class MicroSD card (64GB+) for the best random I/O performance with SQLite.
