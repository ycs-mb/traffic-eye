# src/reporting/

Evidence packaging, report generation, and email delivery.

## Files

| File | Purpose |
|------|---------|
| `evidence.py` | `EvidencePackager` - creates complete evidence packets from violations |
| `report.py` | `ReportGenerator` - renders human-readable reports using Jinja2 |
| `sender.py` | `EmailSender` - queue-based SMTP email delivery with retry |

## evidence.py - Evidence Packaging

`EvidencePackager` creates self-contained evidence packets when a violation is confirmed.

### Packaging Steps

1. **Extract clip** from the circular frame buffer (configurable seconds before/after the violation timestamp)
2. **Select best N frames** (sorted by detection confidence)
3. **Annotate frames** with bounding boxes, class labels, confidence scores, and metadata overlay
4. **Encode as JPEG** (quality 95) and save to the evidence directory
5. **Generate video clip** (MP4) from the frame sequence using OpenCV VideoWriter or FFmpeg fallback
6. **Compute SHA256 hashes** for every evidence file (integrity verification)
7. **Persist to database** - violation record + evidence file records

### Evidence Directory Structure

```
data/evidence/
└── <violation-uuid>/
    ├── frame_00.jpg      # Best evidence frame (annotated)
    ├── frame_01.jpg      # Second best frame
    ├── frame_02.jpg      # Third best frame
    └── clip.mp4          # Video clip (2s before to 3s after violation)
```

### Video Encoding

Two encoding paths:
1. **OpenCV VideoWriter** (primary) - uses `mp4v` fourcc
2. **FFmpeg pipe** (fallback) - raw BGR frames piped to FFmpeg with libx264, fast preset

On Raspberry Pi, FFmpeg can use the V4L2 M2M hardware encoder for better performance.

### Frame Annotation

Each evidence frame includes:
- Bounding boxes around detected objects (red for persons/motorcycles, green for others)
- Class name and confidence score labels
- Bottom overlay bar with: violation type, confidence, GPS coordinates, plate text

## report.py - Report Generation

`ReportGenerator` creates formatted violation reports from evidence packets.

### Output Formats

- **HTML email** - Rendered from `config/email_template.html` (Jinja2)
- **Plain text** - Fallback format with structured fields
- **Attachments** - Best evidence frames as JPEG attachments

### Report Contents

| Field | Description |
|-------|-------------|
| Violation ID | UUID |
| Violation Type | Display name (e.g., "Riding Without Helmet") |
| Date/Time (IST) | Timestamp in Indian Standard Time |
| Location | GPS coordinates with Google Maps link |
| License Plate | OCR text with confidence percentage |
| Overall Confidence | Aggregated confidence score |
| Cloud Verification | Whether confirmed by Gemini/GPT-4V |

### Disclaimer

Every report includes a disclaimer that the evidence is from an automated system and should be reviewed by a human before enforcement action.

## sender.py - Email Sender

`EmailSender` handles SMTP email delivery with production-grade reliability features.

### Features

- **Queue-based**: Reads pending emails from the SQLite `email_queue` table
- **Retry with exponential backoff**: Up to 5 attempts per email, with delays of 2s, 4s, 8s, 16s, 32s (capped at 300s)
- **Rate limiting**: Configurable maximum emails per hour (default: 20)
- **SMTP/TLS**: Connects via STARTTLS on port 587
- **MIME multipart**: HTML + plain text body with JPEG attachments

### Email Configuration

Set in `config/settings.yaml`:

```yaml
reporting:
  email:
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    sender: "your-email@gmail.com"
    password_env: "TRAFFIC_EYE_EMAIL_PASSWORD"
    recipients:
      - "recipient@example.com"
```

The password is read from the environment variable specified by `password_env`.

### Queue Processing

The sender processes pending emails from the database queue:

```python
sender = EmailSender(config, db)
sent_count = sender.process_queue()  # Processes up to 20 pending emails
```

On Raspberry Pi, the queue is processed every 5 minutes by the `traffic-eye-sender.timer` systemd unit.

### Gmail Setup

1. Enable 2-Step Verification on your Google Account
2. Generate an App Password: Google Account -> Security -> App Passwords
3. Export it:
   ```bash
   export TRAFFIC_EYE_EMAIL_PASSWORD="your-16-char-app-password"
   ```

## Deployment on Raspberry Pi

Evidence is stored at `/var/lib/traffic-eye/evidence/` with automatic cleanup when disk usage exceeds 80%. The `StorageManager` in `src/utils/storage.py` handles retention policies.

Email sending runs as a separate systemd oneshot service triggered every 5 minutes, decoupled from the main detection loop to avoid blocking.
