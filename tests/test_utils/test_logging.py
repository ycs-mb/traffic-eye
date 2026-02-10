"""Tests for logging configuration."""

import logging

from src.utils.logging_config import setup_logging


class TestSetupLogging:
    def test_creates_log_dir(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logging(str(log_dir), level="DEBUG")
        assert log_dir.exists()

    def test_creates_log_file(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logging(str(log_dir), level="DEBUG")
        log_file = log_dir / "traffic-eye.log"
        # Write a log message
        logger = logging.getLogger("test")
        logger.info("Test message")
        assert log_file.exists()

    def test_json_format(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logging(str(log_dir), level="DEBUG", json_format=True)
        logger = logging.getLogger("test.json")
        logger.info("JSON test")
        log_file = log_dir / "traffic-eye.log"
        content = log_file.read_text()
        assert '"message"' in content or '"level"' in content

    def test_log_level(self, tmp_path):
        log_dir = tmp_path / "logs"
        setup_logging(str(log_dir), level="WARNING")
        root = logging.getLogger()
        assert root.level == logging.WARNING
