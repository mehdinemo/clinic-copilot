"""Logging configuration for Clinic Operations Assistant.

Configures dual-output logging:
1. Console: Restricted to ERROR and CRITICAL levels to keep CLI uncluttered.
2. File: RotatingFileHandler writing to logs/assistant.log capturing DEBUG, INFO, WARNING,
   ERROR, and CRITICAL for developer debugging.
3. Warnings: Captures Python standard library warnings and routes them through logging.
"""

from __future__ import annotations

import logging
import sys
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional, Sequence, Union

DEFAULT_LOG_DIR = Path("logs")
DEFAULT_LOG_FILE = "assistant.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 3
DEFAULT_CONSOLE_LEVEL = logging.ERROR
DEFAULT_FILE_LEVEL = logging.DEBUG

CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Third-party logger namespaces to route cleanly to root
KNOWN_THIRD_PARTY_LOGGERS: Sequence[str] = (
    "httpx",
    "httpcore",
    "urllib3",
    "langchain",
    "langchain_core",
    "langgraph",
    "openai",
    "google",
    "google.genai",
    "google_genai",
)

_active_log_file: Optional[Path] = None


def get_log_file_path() -> Path:
    """Return the currently configured log file path or the default."""
    if _active_log_file is not None:
        return _active_log_file
    return DEFAULT_LOG_DIR / DEFAULT_LOG_FILE


def setup_logging(
    log_dir: Union[str, Path] = DEFAULT_LOG_DIR,
    log_file: str = DEFAULT_LOG_FILE,
    console_level: int = DEFAULT_CONSOLE_LEVEL,
    file_level: int = DEFAULT_FILE_LEVEL,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    capture_warnings: bool = True,
    console_stream: Optional[Any] = None,
) -> Path:
    """Configure centralized logging with restricted console output and rotating file logging.

    Args:
        log_dir: Directory where the log file should be stored.
        log_file: Name of the rotating log file.
        console_level: Minimum logging level for terminal output (default: ERROR).
        file_level: Minimum logging level for file output (default: DEBUG).
        max_bytes: Maximum size of the log file before rotating (default: 5MB).
        backup_count: Number of backup log files to retain (default: 3).
        capture_warnings: Whether to capture Python warnings and route them to logging.
        console_stream: Output stream for console handler (default: sys.stderr).

    Returns:
        The Path to the configured rotating log file.
    """
    global _active_log_file

    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / log_file
    _active_log_file = file_path

    # Route Python standard library warnings into logging (py.warnings logger)
    if capture_warnings:
        logging.captureWarnings(False)
        logging.captureWarnings(True)
        # Route stdlib warnings into py.warnings without silencing third-party deprecations
        warnings.simplefilter("default")
        # Ignore interpreter shutdown garbage collection resource warnings
        warnings.filterwarnings("ignore", category=ResourceWarning)
    else:
        logging.captureWarnings(False)

    root_logger = logging.getLogger()
    # Root logger level must accept the lowest handler level
    root_logger.setLevel(min(console_level, file_level))

    # Remove existing handlers previously added by this module or default basicConfig
    for handler in list(root_logger.handlers):
        # Do not remove pytest internal capture handlers
        if handler.__class__.__name__ == "LogCaptureHandler":
            continue
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    # 1. Console Handler: Restrict to ERROR and CRITICAL
    stream = console_stream if console_stream is not None else sys.stderr
    console_handler = logging.StreamHandler(stream)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, datefmt=DATE_FORMAT))
    setattr(console_handler, "_is_clinic_logging_handler", True)
    root_logger.addHandler(console_handler)

    # 2. File Handler: RotatingFileHandler capturing DEBUG, INFO, WARNING, ERROR, CRITICAL
    file_handler = RotatingFileHandler(
        filename=str(file_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=DATE_FORMAT))
    setattr(file_handler, "_is_clinic_logging_handler", True)
    root_logger.addHandler(file_handler)

    # 3. Synchronize third-party loggers to propagate cleanly without separate console handlers
    for name in KNOWN_THIRD_PARTY_LOGGERS:
        third_party_logger = logging.getLogger(name)
        third_party_logger.setLevel(file_level)
        third_party_logger.propagate = True
        for h in list(third_party_logger.handlers):
            if isinstance(h, logging.StreamHandler):
                third_party_logger.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    pass

    return file_path
