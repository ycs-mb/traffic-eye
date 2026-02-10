import pytest
import numpy as np
from datetime import datetime, timezone


@pytest.fixture
def test_config_dir(tmp_path):
    """Creates a temporary config directory with test settings."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    settings = config_dir / "settings.yaml"
    settings.write_text("""
camera:
  resolution: [640, 480]
  fps: 30
  process_every_nth_frame: 5
  buffer_seconds: 5

detection:
  model_path: "models/yolov8n_int8.tflite"
  confidence_threshold: 0.5
  nms_threshold: 0.45
  num_threads: 2
  target_classes:
    - person
    - motorcycle
    - car
    - truck
    - bus
    - bicycle
    - traffic light

helmet:
  model_path: "models/helmet_cls_int8.tflite"
  confidence_threshold: 0.85

ocr:
  engine: "paddleocr"
  confidence_threshold: 0.6

violations:
  cooldown_seconds: 30
  max_reports_per_hour: 20

gps:
  required: false
  speed_gate_kmh: 5

reporting:
  evidence_dir: "{evidence_dir}"
  queue_dir: "{queue_dir}"
  best_frames_count: 3
  clip_before_seconds: 2
  clip_after_seconds: 3
  email:
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    sender: "test@example.com"
    password_env: "TRAFFIC_EYE_EMAIL_PASSWORD"
    recipients:
      - "police@example.com"

cloud:
  provider: "gemini"
  api_key_env: "TRAFFIC_EYE_CLOUD_API_KEY"
  confidence_threshold: 0.96
  max_retries: 3
  timeout_seconds: 30

storage:
  max_usage_percent: 80
  evidence_retention_days: 30
  non_violation_retention_hours: 1

thermal:
  throttle_temp_c: 75
  pause_temp_c: 80
  pause_duration_seconds: 30

logging:
  level: "DEBUG"
  json_format: false
  log_dir: "{log_dir}"

platform: "mock"
""".format(
        evidence_dir=str(tmp_path / "evidence"),
        queue_dir=str(tmp_path / "queue"),
        log_dir=str(tmp_path / "logs"),
    ))

    rules = config_dir / "violation_rules.yaml"
    rules.write_text("""
rules:
  no_helmet:
    enabled: true
    min_consecutive_frames: 3
    confidence_threshold: 0.85
    required_detections:
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
    min_duration_seconds: 3
    confidence_threshold: 0.70
    gps_heading_deviation_degrees: 120
    description: "Driving on wrong side of road"
""")

    # Create data dirs
    (tmp_path / "evidence").mkdir(exist_ok=True)
    (tmp_path / "queue").mkdir(exist_ok=True)
    (tmp_path / "logs").mkdir(exist_ok=True)

    return config_dir


@pytest.fixture
def sample_frame():
    """Returns a 640x480 BGR numpy array with a synthetic scene."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Blue sky top half
    frame[:240, :] = [200, 150, 100]
    # Gray road bottom half
    frame[240:, :] = [80, 80, 80]
    return frame


@pytest.fixture
def sample_timestamp():
    """Returns a fixed UTC timestamp for deterministic tests."""
    return datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def tmp_db_path(tmp_path):
    """Returns a path for a temporary SQLite database."""
    return str(tmp_path / "test.db")
