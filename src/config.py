"""Configuration management for traffic-eye."""

from __future__ import annotations

import logging
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is invalid."""


@dataclass(frozen=True)
class CameraConfig:
    resolution: tuple[int, int] = (1280, 720)
    fps: int = 30
    process_every_nth_frame: int = 5
    buffer_seconds: int = 10


@dataclass(frozen=True)
class DetectionConfig:
    model_path: str = "models/yolov8n_int8.tflite"
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.45
    num_threads: int = 4
    target_classes: tuple[str, ...] = (
        "person", "motorcycle", "car", "truck", "bus", "bicycle", "traffic light"
    )


@dataclass(frozen=True)
class HelmetConfig:
    model_path: str = "models/helmet_cls_int8.tflite"
    confidence_threshold: float = 0.85


@dataclass(frozen=True)
class OCRConfig:
    engine: str = "paddleocr"  # "paddleocr" | "tesseract" | "cloud_only"
    confidence_threshold: float = 0.6
    cloud_only: bool = False  # Skip local OCR, use cloud verification for all plates


@dataclass(frozen=True)
class ViolationsConfig:
    cooldown_seconds: int = 30
    max_reports_per_hour: int = 20


@dataclass(frozen=True)
class GPSConfig:
    enabled: bool = True
    required: bool = True
    speed_gate_kmh: float = 5.0
    source: str = "auto"  # "auto" | "gpsd" | "network" | "mock"
    network_host: str = "0.0.0.0"
    network_port: int = 10110
    network_protocol: str = "udp"  # "udp" | "tcp"


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    sender: str = ""
    password_env: str = "TRAFFIC_EYE_EMAIL_PASSWORD"
    recipients: tuple[str, ...] = ()

    @property
    def password(self) -> Optional[str]:
        return os.environ.get(self.password_env)


@dataclass(frozen=True)
class ReportingConfig:
    evidence_dir: str = "data/evidence"
    queue_dir: str = "data/queue"
    best_frames_count: int = 3
    clip_before_seconds: int = 2
    clip_after_seconds: int = 3
    email: EmailConfig = field(default_factory=EmailConfig)


@dataclass(frozen=True)
class CloudConfig:
    provider: str = "gemini"  # "gemini" | "openai" | "vertex_ai"
    api_key_env: str = "TRAFFIC_EYE_CLOUD_API_KEY"
    confidence_threshold: float = 0.96
    max_retries: int = 3
    timeout_seconds: int = 30
    # Vertex AI specific settings
    gcp_project_id: str = ""
    gcp_location: str = "us-central1"

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


@dataclass(frozen=True)
class StorageConfig:
    max_usage_percent: int = 80
    evidence_retention_days: int = 30
    non_violation_retention_hours: int = 1


@dataclass(frozen=True)
class ThermalConfig:
    throttle_temp_c: float = 75.0
    pause_temp_c: float = 80.0
    pause_duration_seconds: int = 30


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    json_format: bool = False
    log_dir: str = "data/logs"


@dataclass(frozen=True)
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    helmet: HelmetConfig = field(default_factory=HelmetConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    violations: ViolationsConfig = field(default_factory=ViolationsConfig)
    gps: GPSConfig = field(default_factory=GPSConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    thermal: ThermalConfig = field(default_factory=ThermalConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    platform: str = "auto"


def _build_sub_config(cls: type, data: dict[str, Any]) -> Any:
    """Build a frozen dataclass from a dict, ignoring unknown keys."""
    if not data:
        return cls()
    valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
    filtered = {}
    for k, v in data.items():
        if k in valid_fields:
            f = cls.__dataclass_fields__[k]
            # Convert lists to tuples for frozen dataclasses
            if f.type in ("tuple[str, ...]",) and isinstance(v, list):
                v = tuple(v)
            # Convert list to tuple for resolution
            if k == "resolution" and isinstance(v, list):
                v = tuple(v)
            filtered[k] = v
    return cls(**filtered)


def load_config(config_dir: str = "config") -> AppConfig:
    """Load configuration from YAML files.

    Args:
        config_dir: Path to the config directory containing settings.yaml.

    Returns:
        Frozen AppConfig instance.

    Raises:
        ConfigError: If settings.yaml is missing or invalid.
    """
    config_path = Path(config_dir) / "settings.yaml"
    if not config_path.exists():
        raise ConfigError(f"Settings file not found: {config_path}")

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f) or {}

    # Build nested config objects
    email_data = raw.get("reporting", {}).get("email", {})
    if isinstance(email_data.get("recipients"), list):
        email_data["recipients"] = tuple(email_data["recipients"])
    email_config = _build_sub_config(EmailConfig, email_data)

    reporting_data = raw.get("reporting", {})
    reporting_data.pop("email", None)
    reporting_config = ReportingConfig(
        **{k: v for k, v in reporting_data.items()
           if k in ReportingConfig.__dataclass_fields__},
        email=email_config,
    )

    detection_data = raw.get("detection", {})
    if isinstance(detection_data.get("target_classes"), list):
        detection_data["target_classes"] = tuple(detection_data["target_classes"])

    camera_data = raw.get("camera", {})
    if isinstance(camera_data.get("resolution"), list):
        camera_data["resolution"] = tuple(camera_data["resolution"])

    config = AppConfig(
        camera=_build_sub_config(CameraConfig, camera_data),
        detection=_build_sub_config(DetectionConfig, detection_data),
        helmet=_build_sub_config(HelmetConfig, raw.get("helmet", {})),
        ocr=_build_sub_config(OCRConfig, raw.get("ocr", {})),
        violations=_build_sub_config(ViolationsConfig, raw.get("violations", {})),
        gps=_build_sub_config(GPSConfig, raw.get("gps", {})),
        reporting=reporting_config,
        cloud=_build_sub_config(CloudConfig, raw.get("cloud", {})),
        storage=_build_sub_config(StorageConfig, raw.get("storage", {})),
        thermal=_build_sub_config(ThermalConfig, raw.get("thermal", {})),
        logging=_build_sub_config(LoggingConfig, raw.get("logging", {})),
        platform=raw.get("platform", "auto"),
    )

    logger.info("Configuration loaded from %s", config_path)
    return config


def detect_platform() -> str:
    """Detect the current platform for selecting implementations."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux" and machine in ("aarch64", "armv7l"):
        return "pi"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    return "unknown"


def resolve_platform(config: AppConfig) -> str:
    """Resolve 'auto' platform to actual platform string."""
    if config.platform == "auto":
        return detect_platform()
    return config.platform
