# config/

Configuration files for Traffic-Eye. All runtime behavior is controlled through these YAML files and the HTML email template.

## Files

| File | Purpose |
|------|---------|
| `settings.yaml` | Main application configuration (camera, detection, reporting, etc.) |
| `violation_rules.yaml` | Per-violation-type rules (thresholds, required detections) |
| `email_template.html` | Jinja2 HTML template for violation report emails |

## settings.yaml Reference

### camera

```yaml
camera:
  resolution: [1280, 720]         # Capture resolution [width, height]
  fps: 30                         # Raw camera FPS
  process_every_nth_frame: 5      # Only run detection on every Nth frame (effective ~6 fps)
  buffer_seconds: 10              # Rolling frame buffer duration for evidence extraction
```

Lowering `process_every_nth_frame` increases detection rate but uses more CPU. On Pi 4, values of 4-6 give the best balance.

### detection

```yaml
detection:
  model_path: "models/yolov8n_int8.tflite"   # Path to YOLOv8n INT8 TFLite model
  confidence_threshold: 0.5                   # Minimum detection confidence
  nms_threshold: 0.45                         # Non-maximum suppression IoU threshold
  num_threads: 4                              # TFLite inference threads (match Pi core count)
  target_classes:                             # COCO classes to detect
    - person
    - motorcycle
    - car
    - truck
    - bus
    - bicycle
    - traffic light
```

### helmet

```yaml
helmet:
  model_path: "models/helmet_cls_int8.tflite"  # Path to MobileNetV3 helmet classifier
  confidence_threshold: 0.85                    # Minimum confidence to classify as helmet/no-helmet
```

### ocr

```yaml
ocr:
  engine: "paddleocr"           # OCR engine (paddleocr is the default)
  confidence_threshold: 0.6     # Minimum OCR text confidence
```

### violations

```yaml
violations:
  cooldown_seconds: 30          # Minimum seconds between reports for the same violation type
  max_reports_per_hour: 20      # Rate limit to prevent email flooding
```

### gps

```yaml
gps:
  enabled: false                # Set to true if GPS hardware is connected
  required: false               # If true, app won't start without GPS fix
  speed_gate_kmh: 5             # Ignore violations when GPS speed is below this (stationary)
```

### reporting

```yaml
reporting:
  evidence_dir: "data/evidence"       # Where to save evidence frames and clips
  queue_dir: "data/queue"             # Offline queue directory
  best_frames_count: 3                # Number of best frames to include in reports
  clip_before_seconds: 2              # Video clip: seconds before violation timestamp
  clip_after_seconds: 3               # Video clip: seconds after violation timestamp
  email:
    smtp_host: "smtp.gmail.com"       # SMTP server
    smtp_port: 587                    # SMTP port (587 for TLS)
    use_tls: true                     # Enable STARTTLS
    sender: ""                        # Sender email address
    password_env: "TRAFFIC_EYE_EMAIL_PASSWORD"  # Env var name for SMTP password
    recipients: []                    # List of recipient email addresses
```

To configure email reporting:
1. Set `sender` to your Gmail address
2. Generate an App Password in Google Account settings (Security -> 2-Step Verification -> App Passwords)
3. Export the password: `export TRAFFIC_EYE_EMAIL_PASSWORD="your-app-password"`
4. Add recipient addresses to the `recipients` list

### cloud

```yaml
cloud:
  provider: "gemini"                          # Cloud vision provider: "gemini" or "openai"
  api_key_env: "TRAFFIC_EYE_CLOUD_API_KEY"    # Env var name for API key
  confidence_threshold: 0.96                  # Minimum cloud confidence to confirm violation
  max_retries: 3                              # Retry attempts on API failure
  timeout_seconds: 30                         # API request timeout
```

Confidence routing:
- **>= 0.96**: Reported directly without cloud verification
- **0.70 - 0.96**: Queued for cloud verification via Gemini Vision or GPT-4V
- **< 0.70**: Discarded as unreliable

### storage

```yaml
storage:
  max_usage_percent: 80               # Trigger cleanup when disk usage exceeds this
  evidence_retention_days: 30         # Keep violation evidence for this many days
  non_violation_retention_hours: 1    # Delete non-violation data after this
```

### thermal

```yaml
thermal:
  throttle_temp_c: 75          # Skip extra frames when CPU temperature exceeds this
  pause_temp_c: 80             # Pause detection entirely when CPU exceeds this
  pause_duration_seconds: 30   # How long to pause when overheated
```

### logging

```yaml
logging:
  level: "INFO"                # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  json_format: false           # Use JSON log format (useful for log aggregation)
  log_dir: "data/logs"         # Log file directory
```

### platform

```yaml
platform: "auto"    # Platform detection: "auto", "pi", "macos", "linux", "mock"
```

Set to `"mock"` to run without any hardware (synthetic frames, random detections). The `--mock` CLI flag overrides this to `"mock"`.

## violation_rules.yaml Reference

```yaml
rules:
  no_helmet:
    enabled: true                    # Enable/disable this rule
    min_consecutive_frames: 3        # Must be detected in N consecutive frames
    confidence_threshold: 0.85       # Minimum confidence per frame
    required_detections:             # Object classes that must be present
      - motorcycle
      - person
    description: "Riding motorcycle without helmet"

  red_light_jump:
    enabled: true
    min_consecutive_frames: 5
    confidence_threshold: 0.80
    required_detections:
      - vehicle
      - traffic_light_red
    description: "Jumping red traffic signal"

  wrong_side:
    enabled: true
    min_duration_seconds: 3          # Must persist for N seconds
    confidence_threshold: 0.70
    gps_heading_deviation_degrees: 120   # Heading deviation threshold
    description: "Driving on wrong side of road"
```

## email_template.html

Jinja2 HTML template used by `ReportGenerator` to render violation report emails. Available template variables:

| Variable | Type | Description |
|----------|------|-------------|
| `violation_id` | str | UUID of the violation |
| `violation_type` | str | Display name (e.g., "Riding Without Helmet") |
| `timestamp_ist` | str | Formatted timestamp in IST |
| `gps_lat` | float | Latitude (None if unavailable) |
| `gps_lon` | float | Longitude (None if unavailable) |
| `maps_url` | str | Google Maps link |
| `plate_text` | str | Detected license plate (None if unavailable) |
| `plate_confidence` | float | OCR confidence (0.0-1.0) |
| `overall_confidence` | float | Aggregated violation confidence (0.0-1.0) |
| `cloud_verified` | bool | Whether cloud verification was performed |
| `cloud_provider` | str | Cloud provider name ("gemini" or "openai") |

## Pi-Specific Config

The setup script generates `settings_pi.yaml` with absolute paths appropriate for the Pi deployment layout:

- Model paths: `/opt/traffic-eye/models/...`
- Evidence dir: `/var/lib/traffic-eye/evidence`
- Queue dir: `/var/lib/traffic-eye/queue`
- Log dir: `/var/lib/traffic-eye/logs`
- Platform: `"pi"`

## Usage on Raspberry Pi

```bash
# Run with default config
python -m src.main --config config

# Run with Pi-specific config (generated by setup.sh)
python -m src.main --config config/settings_pi.yaml
```
