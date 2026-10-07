"""Unit tests for centralized logging configuration."""

import logging
import warnings
from io import StringIO
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.logging_config import (
    DEFAULT_BACKUP_COUNT,
    DEFAULT_MAX_BYTES,
    get_log_file_path,
    setup_logging,
)


def test_setup_logging_creates_directory_and_file(tmp_path: Path) -> None:
    """Verify setup_logging creates the target log directory and file."""
    log_dir = tmp_path / "custom_logs"
    log_file = "custom.log"

    assert not log_dir.exists()

    file_path = setup_logging(log_dir=log_dir, log_file=log_file)

    assert log_dir.exists()
    assert log_dir.is_dir()
    assert file_path.exists()
    assert file_path == log_dir / log_file
    assert get_log_file_path() == file_path


def test_console_restricts_to_error_and_critical(tmp_path: Path) -> None:
    """Verify console output only emits ERROR and CRITICAL, suppressing INFO and WARNING."""
    console_buffer = StringIO()
    log_dir = tmp_path / "logs"

    setup_logging(
        log_dir=log_dir,
        log_file="test_console.log",
        console_stream=console_buffer,
    )

    test_logger = logging.getLogger("test_console_logger")
    test_logger.debug("Debug console message")
    test_logger.info("Info console message")
    test_logger.warning("Warning console message")
    test_logger.error("Error console message")
    test_logger.critical("Critical console message")

    output = console_buffer.getvalue()

    assert "Debug console message" not in output
    assert "Info console message" not in output
    assert "Warning console message" not in output
    assert "Error console message" in output
    assert "Critical console message" in output


def test_file_handler_captures_debug_info_warning_and_errors(tmp_path: Path) -> None:
    """Verify rotating file handler captures all log levels (DEBUG, INFO, WARNING, ERROR)."""
    log_dir = tmp_path / "logs"
    log_file = "test_file.log"

    file_path = setup_logging(log_dir=log_dir, log_file=log_file)

    test_logger = logging.getLogger("test_file_logger")
    test_logger.debug("Diagnostic debug event")
    test_logger.info("Informational event")
    test_logger.warning("Cautionary warning event")
    test_logger.error("Failure error event")

    content = file_path.read_text(encoding="utf-8")

    assert "Diagnostic debug event" in content
    assert "Informational event" in content
    assert "Cautionary warning event" in content
    assert "Failure error event" in content


def test_standard_warnings_captured_and_routed_to_file(tmp_path: Path) -> None:
    """Verify warnings from the warnings module are routed to file and silenced from console."""
    console_buffer = StringIO()
    log_dir = tmp_path / "logs"
    log_file = "test_warnings.log"

    file_path = setup_logging(
        log_dir=log_dir,
        log_file=log_file,
        console_stream=console_buffer,
        capture_warnings=True,
    )

    warning_text = "Third-party deprecation warning sample"
    warnings.warn(warning_text, DeprecationWarning)

    console_output = console_buffer.getvalue()
    file_content = file_path.read_text(encoding="utf-8")

    # Console must NOT have the warning
    assert warning_text not in console_output

    # File must capture the warning under py.warnings
    assert warning_text in file_content
    assert "py.warnings" in file_content


def test_rotating_file_handler_specifications(tmp_path: Path) -> None:
    """Verify RotatingFileHandler has 5MB max bytes and 3 backups by default."""
    log_dir = tmp_path / "logs"
    setup_logging(log_dir=log_dir, log_file="test_rotation.log")

    root = logging.getLogger()
    rotating_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]

    assert len(rotating_handlers) == 1
    handler = rotating_handlers[0]

    assert handler.maxBytes == DEFAULT_MAX_BYTES
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == DEFAULT_BACKUP_COUNT
    assert handler.backupCount == 3
    assert handler.level == logging.DEBUG


def test_gitignore_contains_logs_directory() -> None:
    """Verify that .gitignore excludes the logs directory."""
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists()

    content = gitignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]

    assert "logs/" in lines
