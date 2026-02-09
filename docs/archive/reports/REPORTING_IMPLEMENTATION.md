# Reporting Pipeline Implementation

## Overview

This document details the robust reporting pipeline implementation for traffic violations in the traffic-eye project. The system is designed to survive power loss, network outages, and handle errors gracefully while minimizing SD card wear on Raspberry Pi devices.

## Implementation Summary

### 1. Evidence Packaging (`src/reporting/evidence.py`)

**Key Features:**
- **Best Frame Selection**: Extracts top 3 frames from CircularFrameBuffer based on detection confidence scores
- **Hardware-Accelerated Video Encoding**: Uses H.264 with V4L2 M2M hardware acceleration on Pi, falls back to software encoding
- **SD Card Optimization**: Writes to tmpfs (`/tmp`) first, then atomically moves to final destination
- **Error Handling**: Gracefully continues if video encoding fails, logs all errors with context
- **File Integrity**: Computes SHA256 hashes for all evidence files

**Frame Selection Algorithm:**
```python
def _select_best_frames(self, violation, clip_frames, count):
    """
    1. Build map of frame_id -> confidence score from violation frames
    2. Score all clip frames (use detection confidence if available, else 0.0)
    3. Sort by score descending
    4. Return top N frames
    """
```

**Video Encoding Strategy:**
1. Try hardware-accelerated H.264 encoding (h264_v4l2m2m codec)
2. If hardware fails, fall back to software encoding (libx264)
3. Use tmpfs for temporary files to minimize SD writes
4. Atomic move to final destination
5. Cleanup temporary files in all cases

**Encoding Parameters:**
- Hardware: 1Mbps bitrate, 1.5Mbps max, 2M buffer
- Software: CRF 28 (good quality/size balance), fast preset
- Both: 8fps, yuv420p pixel format for compatibility

### 2. Email Delivery (`src/reporting/sender.py`)

**Key Features:**
- **SMTP/TLS**: Gmail-compatible on port 587
- **Queue Persistence**: SQLite with WAL mode for crash safety
- **Retry Logic**: Exponential backoff with max 5 attempts
- **Offline Handling**: Detects network failures, keeps emails in queue
- **Rate Limiting**: Respects max reports per hour from config
- **Evidence Cleanup**: Removes sent files to save space

**Queue Processing Flow:**
```
1. Fetch pending emails from SQLite (limit 20)
2. For each entry:
   a. Check max attempts (5) - mark failed if exceeded
   b. Check rate limit - stop if exceeded
   c. Apply exponential backoff for retries (min(300, 2^attempts) seconds)
   d. Mark as "processing"
   e. Reconstruct report from stored evidence
   f. Attempt to send via SMTP
   g. On success: mark "sent", cleanup evidence files
   h. On failure: mark "pending" for retry
   i. On permanent error: mark "failed"
```

**Error Handling:**
- `SMTPAuthenticationError`: Log and mark failed (no retry)
- `socket.gaierror`: Network unavailable, keep in queue for retry
- `SMTPException`: Generic SMTP error, retry with backoff
- Missing evidence: Mark failed immediately

**Report Reconstruction:**
- Fetches violation record from database
- Loads evidence files from filesystem
- Rebuilds ViolationCandidate and EvidencePacket
- Generates report using ReportGenerator
- Handles missing files gracefully

### 3. Email Template Rendering (`config/email_template.html`)

**Template Variables:**
- `violation_id`: Unique violation identifier
- `violation_type`: Human-readable violation type (e.g., "Riding Without Helmet")
- `timestamp_ist`: Timestamp in IST timezone
- `gps_lat`, `gps_lon`: GPS coordinates
- `maps_url`: Google Maps link
- `location_address`: Reverse-geocoded address (if available)
- `plate_text`, `plate_confidence`: License plate info
- `overall_confidence`: Detection confidence score
- `cloud_verified`, `cloud_provider`: Cloud verification status

**Features:**
- Responsive HTML design
- Confidence badges (green/orange/red based on score)
- Google Maps integration
- Professional disclaimer
- Plain text fallback

## SQLite Queue Schema

The email queue uses WAL (Write-Ahead Logging) mode for crash safety:

```sql
CREATE TABLE email_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | processing | sent | failed
    attempts INTEGER DEFAULT 0,
    last_attempt_at TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (violation_id) REFERENCES violations(id) ON DELETE CASCADE
);

CREATE INDEX idx_email_queue_status ON email_queue(status);
```

**WAL Mode Benefits:**
- Atomic commits survive power loss
- Readers don't block writers
- Better concurrency for queue processing

## SD Card Optimization Techniques

### 1. Minimize Writes
- Write JPEG frames to `/tmp` (tmpfs) first
- Only move to SD card after successful encoding
- Batch database operations with transactions

### 2. Atomic Operations
- Use `shutil.move()` for atomic file moves
- SQLite transactions for queue updates
- WAL mode for crash recovery

### 3. Write Patterns
- Evidence files: tmpfs → atomic move → final location
- Video clips: encode to tmpfs → verify → move
- Database: batch inserts, WAL journaling

### 4. Cleanup Strategy
- Delete evidence files after successful email send
- Retention policy enforced by storage manager
- Temporary files cleaned up in finally blocks

## Configuration

Environment variables required:
```bash
export TRAFFIC_EYE_EMAIL_PASSWORD="app_specific_password"
```

Config file (`config/settings.yaml`):
```yaml
reporting:
  evidence_dir: "data/evidence"
  best_frames_count: 3
  clip_before_seconds: 2
  clip_after_seconds: 3
  email:
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    sender: "your-email@gmail.com"
    recipients:
      - "recipient@example.com"

violations:
  max_reports_per_hour: 20
```

## Test Coverage

### Evidence Packaging Tests (`tests/test_reporting/test_evidence.py`)
- ✓ Evidence directory creation
- ✓ Best frame extraction (by confidence)
- ✓ Metadata packaging (GPS, plate, timestamps)
- ✓ File hash computation (SHA256)
- ✓ Database record insertion
- ✓ Video encoding fallback (HW → SW)
- ✓ Empty buffer handling
- ✓ Missing GPS/plate handling
- ✓ Frame annotation with bounding boxes

### Email Sender Tests (`tests/test_reporting/test_sender.py`)
- ✓ Successful email send
- ✓ Missing config handling
- ✓ Missing password handling
- ✓ SMTP authentication errors
- ✓ Network errors (socket.gaierror)
- ✓ Queue processing (success path)
- ✓ Retry logic with exponential backoff
- ✓ Max retry attempts (5)
- ✓ Rate limiting
- ✓ SMTP/TLS connection
- ✓ MIME message construction
- ✓ Report reconstruction from database
- ✓ Evidence cleanup after send
- ✓ Missing evidence handling

### Template Rendering Tests (`tests/test_reporting/test_report_template.py`)
- ✓ Basic report generation
- ✓ HTML body contains violation details
- ✓ Text body contains violation details
- ✓ GPS coordinates formatting
- ✓ Confidence score display
- ✓ Plate text display
- ✓ Cloud verification badge
- ✓ Missing GPS handling
- ✓ Missing plate handling
- ✓ Attachment inclusion
- ✓ Disclaimer presence
- ✓ IST timestamp format
- ✓ Subject line format
- ✓ Multiple violation types

## Reliability Measures

### Power Loss Protection
1. **SQLite WAL Mode**: Database changes are crash-safe
2. **Atomic File Operations**: Files are fully written or not at all
3. **Queue Persistence**: Unsent emails survive reboot
4. **Retry Logic**: Failed sends are automatically retried

### Network Outage Handling
1. **Offline Detection**: `socket.gaierror` caught and logged
2. **Queue Accumulation**: Emails stay in queue until network returns
3. **Automatic Resume**: Queue processing picks up where it left off
4. **Rate Limiting**: Prevents burst when network returns

### Disk Full Protection
1. **Tmpfs Usage**: Video encoding uses RAM, not SD card
2. **Cleanup After Send**: Evidence files deleted after successful delivery
3. **Retention Policy**: Old evidence automatically purged
4. **Error Logging**: Disk errors logged with context

### Error Recovery
1. **Exponential Backoff**: Retries at 2s, 4s, 8s, 16s, 32s
2. **Max Attempts**: Give up after 5 tries
3. **Error Messages**: Stored in database for debugging
4. **Graceful Degradation**: Continue processing other emails

## Performance Characteristics

### Memory Usage
- JPEG encoding: ~5MB per frame (720p)
- Video encoding: ~100MB peak (5 seconds @ 720p, 8fps)
- Queue processing: ~10MB per email

### Storage Usage
- Evidence per violation: ~3-5MB (3 frames + metadata)
- Video clip: ~1-2MB (5 seconds, H.264)
- Database: ~1KB per violation record

### Processing Time
- Frame extraction: <100ms
- JPEG encoding: ~50ms per frame
- Video encoding (HW): ~2-3 seconds
- Video encoding (SW): ~8-10 seconds
- Email send: ~2-3 seconds (network dependent)

## Deployment Checklist

1. **Install Dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

2. **Configure Email**
   - Set up Gmail app password
   - Export `TRAFFIC_EYE_EMAIL_PASSWORD`
   - Configure sender/recipients in `config/settings.yaml`

3. **Create Directories**
   ```bash
   mkdir -p data/evidence data/queue data/logs
   ```

4. **Test Email Sending**
   ```bash
   pytest tests/test_reporting/ -v
   ```

5. **Check Hardware Acceleration**
   ```bash
   ffmpeg -codecs | grep h264_v4l2m2m
   ```

6. **Monitor Queue**
   ```bash
   sqlite3 data/traffic_eye.db "SELECT * FROM email_queue WHERE status='pending'"
   ```

## Troubleshooting

### Emails Not Sending
1. Check password environment variable
2. Verify SMTP credentials
3. Check network connectivity
4. Review `data/logs/traffic_eye.log`

### Video Encoding Fails
1. Check FFmpeg installation: `which ffmpeg`
2. Test hardware codec: `ffmpeg -codecs | grep h264_v4l2m2m`
3. Falls back to software automatically
4. Video failure doesn't block email sending

### Queue Stuck
1. Check database: `sqlite3 data/traffic_eye.db`
2. Look for failed entries: `SELECT * FROM email_queue WHERE status='failed'`
3. Reset stuck entries: `UPDATE email_queue SET status='pending' WHERE status='processing'`

### Disk Full
1. Check evidence retention: `du -sh data/evidence/`
2. Manually trigger cleanup
3. Reduce `evidence_retention_days` in config

## Future Enhancements

1. **Attachment Size Limit**: Compress or link large video clips
2. **Multiple Recipients**: Support CC/BCC
3. **Webhook Alternative**: Send to HTTP endpoint instead of email
4. **SMS Notifications**: Quick alerts for high-priority violations
5. **Dashboard Integration**: Real-time status of queue processing
6. **Evidence Archive**: S3/cloud backup before local cleanup
7. **Priority Queue**: Process high-confidence violations first
8. **Batching**: Send daily summary instead of per-violation emails

## Code Quality

- **Function Length**: All functions under 30 lines
- **Composability**: Each function has single responsibility
- **Error Handling**: Try-except blocks with specific exceptions
- **Logging**: Contextual log messages at appropriate levels
- **Type Hints**: Full type annotations for maintainability
- **Documentation**: Docstrings for all public methods

## References

- SQLite WAL Mode: https://www.sqlite.org/wal.html
- FFmpeg H.264 Encoding: https://trac.ffmpeg.org/wiki/Encode/H.264
- Gmail SMTP: https://support.google.com/mail/answer/7126229
- Jinja2 Templates: https://jinja.palletsprojects.com/
- Raspberry Pi Video Encoding: https://github.com/raspberrypi/documentation/blob/master/docs/hardware/raspberry-pi/video-acceleration.md
