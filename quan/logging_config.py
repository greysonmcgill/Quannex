"""
QUAN Recovery - Centralized Logging Configuration

This module provides a single source of truth for logging configuration.
Import and call configure_logging() once at application startup instead of
using logging.basicConfig() scattered throughout the codebase.

Usage:
    # In main.py or application entry point:
    from quan.logging_config import configure_logging, get_logger

    configure_logging()
    logger = get_logger(__name__)

    # In other modules:
    from quan.logging_config import get_logger
    logger = get_logger(__name__)
"""

import json
import logging
import logging.handlers
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variable for request correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


# =============================================================================
# CUSTOM FORMATTER
# =============================================================================

class StructuredFormatter(logging.Formatter):
    """
    JSON-structured log formatter for production environments.

    Outputs logs in a format compatible with log aggregation services
    like Datadog, Splunk, or ELK stack.
    """

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if self.include_extra:
            extra_fields = {
                k: v for k, v in record.__dict__.items()
                if k not in {
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "thread", "threadName",
                    "message", "taskName",
                }
                and not k.startswith("_")
            }
            if extra_fields:
                log_entry["extra"] = extra_fields

        return json.dumps(log_entry)


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable formatter for development environments.
    Includes colors if supported by the terminal.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname}{self.RESET}"

        formatted = super().format(record)

        # Add correlation ID if available
        correlation_id = correlation_id_var.get()
        if correlation_id:
            formatted = f"[{correlation_id[:8]}] {formatted}"

        return formatted


# =============================================================================
# CONFIGURATION
# =============================================================================

def configure_logging(
    level: Optional[str] = None,
    json_format: Optional[bool] = None,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configure application-wide logging.

    This should be called once at application startup. It configures the
    root logger and sets up handlers based on environment.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to LOG_LEVEL env var or INFO.
        json_format: Use JSON format for logs. Defaults to True in production.
        log_file: Optional file path for file logging.
        max_bytes: Max size of log file before rotation (default 10MB).
        backup_count: Number of backup files to keep (default 5).
    """
    # Determine settings from environment
    env = os.environ.get("ENVIRONMENT", "development").lower()
    is_production = env in ("production", "prod", "staging")

    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()

    if json_format is None:
        json_format = is_production

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if json_format:
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(DevelopmentFormatter())

    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    root_logger.info(
        "Logging configured",
        extra={
            "level": level,
            "json_format": json_format,
            "environment": env,
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    This is the preferred way to get loggers throughout the application.

    Args:
        name: Logger name, typically __name__ of the module.

    Returns:
        Configured logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Processing account", extra={"account_id": "ACC123"})
    """
    return logging.getLogger(name)


# =============================================================================
# CORRELATION ID MANAGEMENT
# =============================================================================

def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set the correlation ID for the current context.

    Args:
        correlation_id: ID to use, or None to generate a new one.

    Returns:
        The correlation ID that was set.
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID, or None if not set."""
    return correlation_id_var.get()


def clear_correlation_id() -> None:
    """Clear the correlation ID for the current context."""
    correlation_id_var.set(None)


# =============================================================================
# CONTEXT MANAGER
# =============================================================================

class LoggingContext:
    """
    Context manager for adding correlation ID to log messages.

    Usage:
        with LoggingContext(request_id="req-123"):
            logger.info("Processing request")  # Includes correlation ID
    """

    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id
        self._token = None

    def __enter__(self) -> str:
        self.correlation_id = set_correlation_id(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        clear_correlation_id()


# =============================================================================
# LOG ADAPTER FOR EXTRA CONTEXT
# =============================================================================

class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that adds context to all log messages.

    Usage:
        logger = ContextLogger(get_logger(__name__), {"account_id": "ACC123"})
        logger.info("Processing")  # Automatically includes account_id
    """

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        extra = kwargs.get("extra", {})
        extra.update(self.extra)

        # Add correlation ID
        correlation_id = correlation_id_var.get()
        if correlation_id:
            extra["correlation_id"] = correlation_id

        kwargs["extra"] = extra
        return msg, kwargs


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "configure_logging",
    "get_logger",
    "set_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
    "LoggingContext",
    "ContextLogger",
    "StructuredFormatter",
    "DevelopmentFormatter",
]
