from unittest.mock import patch

from loguru import logger

from utils.logger import setup_logging


class TestSetupLogging:
    def test_creates_logs_directory(self, tmp_path):
        logs_dir = tmp_path / "logs"
        with patch("utils.logger.settings") as mock_settings:
            mock_settings.LOGS_DIR = logs_dir
            mock_settings.LOG_LEVEL = "INFO"
            setup_logging()
        assert logs_dir.is_dir()

    def test_adds_two_handlers(self, tmp_path):
        logs_dir = tmp_path / "logs"
        with patch("utils.logger.settings") as mock_settings:
            mock_settings.LOGS_DIR = logs_dir
            mock_settings.LOG_LEVEL = "INFO"
            setup_logging()
        assert len(logger._core.handlers) == 2

    def test_writes_to_log_file(self, tmp_path):
        logs_dir = tmp_path / "logs"
        with patch("utils.logger.settings") as mock_settings:
            mock_settings.LOGS_DIR = logs_dir
            mock_settings.LOG_LEVEL = "DEBUG"
            setup_logging()
        logger.info("hello from test")
        log_files = list(logs_dir.glob("pipeline_*.log"))
        assert len(log_files) == 1
        assert "hello from test" in log_files[0].read_text()

    def test_file_captures_debug_even_when_console_is_higher(self, tmp_path):
        logs_dir = tmp_path / "logs"
        with patch("utils.logger.settings") as mock_settings:
            mock_settings.LOGS_DIR = logs_dir
            mock_settings.LOG_LEVEL = "WARNING"
            setup_logging()
        logger.debug("debug only in file")
        log_files = list(logs_dir.glob("pipeline_*.log"))
        assert len(log_files) == 1
        assert "debug only in file" in log_files[0].read_text()

    def test_idempotent_call(self, tmp_path):
        logs_dir = tmp_path / "logs"
        with patch("utils.logger.settings") as mock_settings:
            mock_settings.LOGS_DIR = logs_dir
            mock_settings.LOG_LEVEL = "INFO"
            setup_logging()
            setup_logging()
        assert len(logger._core.handlers) == 2
