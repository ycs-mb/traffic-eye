"""Tests for configuration management."""

from src.config import AppConfig, ConfigError, load_config, detect_platform


class TestLoadConfig:
    def test_load_valid_config(self, test_config_dir):
        config = load_config(str(test_config_dir))
        assert config.camera.resolution == (640, 480)
        assert config.camera.fps == 30
        assert config.detection.confidence_threshold == 0.5
        assert config.helmet.confidence_threshold == 0.85
        assert config.platform == "mock"

    def test_missing_config_file(self, tmp_path):
        try:
            load_config(str(tmp_path / "nonexistent"))
            assert False, "Should have raised ConfigError"
        except ConfigError:
            pass

    def test_defaults(self):
        config = AppConfig()
        assert config.camera.resolution == (1280, 720)
        assert config.camera.fps == 30
        assert config.thermal.throttle_temp_c == 75.0

    def test_frozen(self):
        config = AppConfig()
        try:
            config.platform = "test"
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass

    def test_email_recipients_tuple(self, test_config_dir):
        config = load_config(str(test_config_dir))
        assert isinstance(config.reporting.email.recipients, tuple)

    def test_detection_classes_tuple(self, test_config_dir):
        config = load_config(str(test_config_dir))
        assert isinstance(config.detection.target_classes, tuple)
        assert "person" in config.detection.target_classes


class TestDetectPlatform:
    def test_returns_string(self):
        result = detect_platform()
        assert isinstance(result, str)
        assert result in ("pi", "macos", "linux", "unknown")
