"""Factory functions for creating platform-specific component implementations."""

from __future__ import annotations

import logging
from typing import Optional

from src.capture.camera import CameraBase, MockCamera, OpenCVCamera, VideoFileCamera
from src.capture.gps import GPSBase, MockGPS
from src.config import AppConfig, resolve_platform
from src.detection.detector import DetectorBase, MockDetector
from src.detection.helmet import HelmetClassifierBase, MockHelmetClassifier
from src.utils.thermal import MockThermalMonitor, PsutilThermalMonitor, ThermalMonitorBase

logger = logging.getLogger(__name__)


def create_camera(config: AppConfig, video_file: Optional[str] = None) -> CameraBase:
    """Create a camera instance based on platform."""
    platform = resolve_platform(config)

    if video_file:
        logger.info("Using video file camera: %s", video_file)
        return VideoFileCamera(video_file)

    if platform == "mock":
        logger.info("Using mock camera")
        return MockCamera(
            resolution=config.camera.resolution,
            fps=config.camera.fps,
        )

    if platform == "pi":
        try:
            from src.capture.camera import PiCamera
            logger.info("Using PiCamera2")
            return PiCamera(
                resolution=config.camera.resolution,
                fps=config.camera.fps,
            )
        except ImportError:
            logger.warning("picamera2 not available, falling back to OpenCV")

    logger.info("Using OpenCV camera (device 0)")
    return OpenCVCamera(
        device_id=0,
        resolution=config.camera.resolution,
        fps=config.camera.fps,
    )


def create_gps(config: AppConfig) -> GPSBase:
    """Create a GPS reader based on config source and platform."""
    if not config.gps.enabled:
        logger.info("GPS disabled in config")
        return MockGPS()

    source = config.gps.source

    # Explicit source selection
    if source == "mock":
        logger.info("Using mock GPS (source=mock)")
        return MockGPS()

    if source == "network":
        try:
            from src.capture.gps import NetworkGPS
            logger.info(
                "Using NetworkGPS (%s://%s:%d)",
                config.gps.network_protocol,
                config.gps.network_host,
                config.gps.network_port,
            )
            return NetworkGPS(
                host=config.gps.network_host,
                port=config.gps.network_port,
                protocol=config.gps.network_protocol,
            )
        except ImportError:
            logger.error("pynmea2 not installed. Install with: pip install pynmea2")
            return MockGPS()

    if source == "gpsd":
        try:
            from src.capture.gps import GpsdGPS
            logger.info("Using GpsdGPS (source=gpsd)")
            return GpsdGPS()
        except ImportError:
            logger.warning("gps3 not available, falling back to mock GPS")
            return MockGPS()

    # source == "auto": platform-based logic
    platform = resolve_platform(config)

    if platform == "mock":
        logger.info("Using mock GPS (platform=mock)")
        return MockGPS()

    if platform == "pi":
        try:
            from src.capture.gps import GpsdGPS
            logger.info("Using GpsdGPS (platform=pi)")
            return GpsdGPS()
        except ImportError:
            logger.warning("gps3 not available, falling back to mock GPS")

    logger.info("GPS not available on this platform, using mock")
    return MockGPS()


def create_detector(config: AppConfig) -> DetectorBase:
    """Create an object detector based on platform."""
    platform = resolve_platform(config)

    if platform == "mock":
        logger.info("Using mock detector (random mode)")
        det = MockDetector(random_mode=True)
        det.load_model("")
        return det

    # Try TFLite
    try:
        from src.detection.detector import TFLiteDetector
        det = TFLiteDetector(
            confidence_threshold=config.detection.confidence_threshold,
            nms_threshold=config.detection.nms_threshold,
            num_threads=config.detection.num_threads,
            target_classes=config.detection.target_classes,
        )
        det.load_model(config.detection.model_path)
        return det
    except (ImportError, RuntimeError, OSError) as e:
        logger.warning("TFLite detector not available (%s), using mock", e)
        det = MockDetector(random_mode=True)
        det.load_model("")
        return det


def create_helmet_classifier(config: AppConfig) -> HelmetClassifierBase:
    """Create a helmet classifier based on platform."""
    platform = resolve_platform(config)

    if platform == "mock":
        logger.info("Using mock helmet classifier")
        cls = MockHelmetClassifier()
        cls.load_model("")
        return cls

    try:
        from src.detection.helmet import TFLiteHelmetClassifier
        cls = TFLiteHelmetClassifier()
        cls.load_model(config.helmet.model_path)
        return cls
    except (ImportError, RuntimeError, OSError) as e:
        logger.warning("TFLite helmet classifier not available (%s), using mock", e)
        cls = MockHelmetClassifier()
        cls.load_model("")
        return cls


def create_thermal_monitor(config: AppConfig) -> ThermalMonitorBase:
    """Create a thermal monitor based on platform."""
    platform = resolve_platform(config)

    if platform == "mock":
        return MockThermalMonitor()

    if platform == "pi":
        from src.utils.thermal import VcgencmdThermalMonitor
        logger.info("Using vcgencmd thermal monitor")
        return VcgencmdThermalMonitor()

    return PsutilThermalMonitor()
