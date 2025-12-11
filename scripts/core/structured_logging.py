#!/usr/bin/env python3
"""
Structured Logging Module with JSON Output and Context Support.

This module provides structured logging capabilities that integrate with
the existing logging system while adding:
- JSON-formatted log output for log aggregation systems
- Contextual logging with bound parameters
- Privacy-aware logging with automatic PHI redaction
- Integration with encrypted logging for sensitive operations

Best Practices:
- Use structured loggers for all new code
- Always include contextual information (user_id, request_id, etc.)
- Never log raw PHI/PII - use aggregate values or hashes
- Use log_context() for request-scoped context

Architecture:
    This module bridges the existing scripts/utils/logging.py with
    modern structured logging patterns. It wraps the existing logger
    while adding structured output capabilities.

Usage:
    >>> from scripts.core import get_structured_logger, log_context
    >>> logger = get_structured_logger(__name__)

    # Basic structured logging
    >>> logger.info("Processing started", file_count=10, batch_id="abc123")

    # With context manager for request-scoped data
    >>> with log_context(request_id="req-123", user="analyst"):
    ...     logger.info("Query executed", query_type="aggregate")

See Also:
    - scripts/utils/logging.py - Base logging implementation
    - server/ - MCP server implementation with secure logging
"""

from __future__ import annotations

import contextvars
import json
import logging
import threading
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

# Public API
__all__ = [
    # PHI utilities
    "PHI_PATTERNS",
    "BoundLogger",
    "JSONFormatter",
    # Core classes
    "StructuredLogger",
    "_is_phi_key",
    "_redact_phi",  # Exposed for log_decryptor.py
    "clear_context",
    "configure_logging",
    "get_current_context",
    # Factory functions
    "get_structured_logger",
    # Context management
    "log_context",
    "set_context",
    "setup_structured_logging",
]

# Context variable for request-scoped log context
_log_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "log_context", default={}
)

# Thread-local storage for non-async contexts
_thread_context = threading.local()


# PHI patterns for automatic redaction (aligned with deidentify.py PHIType)
PHI_PATTERNS: frozenset[str] = frozenset(
    {
        "name",
        "ssn",
        "mrn",
        "dob",
        "birth",
        "address",
        "phone",
        "email",
        "patient",
        "street",
        "city",
        "zip",
        "account",
        "license",
        "device",
        "ip_address",
        "mac_address",
        "biometric",
        "photo",
        "fax",
        "url",
        "vehicle",
    }
)


def _is_phi_key(key: str) -> bool:
    """Check if a key potentially contains PHI based on naming patterns.

    Args:
        key: Dictionary key name to check.

    Returns:
        True if the key matches known PHI patterns, False otherwise.
    """
    key_lower = key.lower().replace("_", "").replace("-", "")
    return any(pattern in key_lower for pattern in PHI_PATTERNS)


def _redact_phi(data: dict[str, Any], redact: bool = True) -> dict[str, Any]:
    """Redact PHI values from a dictionary.

    Args:
        data: Dictionary potentially containing PHI.
        redact: Whether to apply redaction (pass False to skip).

    Returns:
        Dictionary with PHI values replaced with '[REDACTED]'.
        Nested dictionaries are processed recursively.
    """
    if not redact:
        return data

    result = {}
    for key, value in data.items():
        if _is_phi_key(key):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = _redact_phi(value, redact)
        else:
            result[key] = value
    return result


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured log output.

    Produces JSON-formatted log records suitable for log aggregation
    systems like ELK, Splunk, or CloudWatch.

    Output includes:
        - timestamp: ISO 8601 format with timezone
        - level: Log level name
        - logger: Logger name (module path)
        - message: Log message
        - context: Bound context parameters
        - extra: Additional parameters from log call
        - error: Exception info if present
    """

    def __init__(
        self,
        *,
        include_timestamp: bool = True,
        redact_phi: bool = True,
        indent: int | None = None,
    ) -> None:
        """Initialize JSON formatter.

        Args:
            include_timestamp: Include ISO timestamp in output
            redact_phi: Automatically redact PHI patterns
            indent: JSON indentation (None for compact)
        """
        super().__init__()
        self.include_timestamp = include_timestamp
        self.redact_phi = redact_phi
        self.indent = indent

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Python logging LogRecord to format.

        Returns:
            JSON-encoded string representation of the log entry.
        """
        # Build base log entry
        log_entry: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add timestamp
        if self.include_timestamp:
            log_entry["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Add source location for errors
        if record.levelno >= logging.ERROR:
            log_entry["location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add context from context variable
        ctx = get_current_context()
        if ctx:
            log_entry["context"] = _redact_phi(ctx, self.redact_phi)

        # Add extra fields from record
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "taskName",
                "message",
            }
        }
        if extra_fields:
            log_entry["extra"] = _redact_phi(extra_fields, self.redact_phi)

        # Add exception info
        if record.exc_info:
            log_entry["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_entry, default=str, indent=self.indent)


class StructuredLogger:
    """Structured logger wrapper with context binding and PHI redaction.

    This logger wraps the standard Python logger while providing:
    - Automatic context binding from log_context()
    - PHI-aware logging with automatic redaction
    - Structured extra parameters
    - Integration with existing project logging

    Example:
        >>> logger = StructuredLogger(__name__)
        >>> logger.info("Query executed", query_type="aggregate", row_count=100)

    Note:
        This is a wrapper around the standard logger, not a replacement.
        The underlying logger is obtained from the existing logging setup.
    """

    def __init__(
        self,
        name: str,
        *,
        redact_phi: bool = True,
    ) -> None:
        """Initialize structured logger.

        Args:
            name: Logger name (typically __name__)
            redact_phi: Automatically redact PHI patterns in extra args
        """
        self.name = name
        self.redact_phi = redact_phi
        self._logger: logging.Logger | None = None

    @property
    def logger(self) -> logging.Logger:
        """Get the underlying Python logger (lazy initialization)."""
        if self._logger is None:
            # Import here to avoid circular imports
            from scripts.utils.logging import get_logger

            self._logger = get_logger(self.name)
        return self._logger

    def _log(
        self,
        level: int,
        msg: str,
        *args: Any,
        exc_info: Any = None,
        **kwargs: Any,
    ) -> None:
        """Internal log method with structured extra handling."""
        # Get current context
        ctx = get_current_context()

        # Merge context with extra kwargs
        extra = {**ctx, **kwargs}

        # Redact PHI if enabled
        if self.redact_phi:
            extra = _redact_phi(extra, True)

        # Log with extra as separate dict to avoid conflicts
        if extra:
            # Create a new record with extra data
            self.logger.log(level, msg, *args, exc_info=exc_info, extra=extra)
        else:
            self.logger.log(level, msg, *args, exc_info=exc_info)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log DEBUG message with structured extras."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log INFO message with structured extras."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log WARNING message with structured extras."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(
        self, msg: str, *args: Any, exc_info: Any = None, **kwargs: Any
    ) -> None:
        """Log ERROR message with structured extras."""
        self._log(logging.ERROR, msg, *args, exc_info=exc_info, **kwargs)

    def critical(
        self, msg: str, *args: Any, exc_info: Any = None, **kwargs: Any
    ) -> None:
        """Log CRITICAL message with structured extras."""
        self._log(logging.CRITICAL, msg, *args, exc_info=exc_info, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log ERROR message with exception info."""
        self._log(logging.ERROR, msg, *args, exc_info=True, **kwargs)

    def bind(self, **kwargs: Any) -> BoundLogger:
        """Create a new logger with bound context.

        Args:
            **kwargs: Context to bind to all log calls

        Returns:
            BoundLogger with bound context

        Example:
            >>> bound = logger.bind(request_id="abc123")
            >>> bound.info("Processing")  # Includes request_id
        """
        return BoundLogger(self, kwargs)


class BoundLogger:
    """Logger with permanently bound context.

    Created by StructuredLogger.bind() to provide context that
    is automatically included in all log calls.

    Attributes:
        _logger: Parent StructuredLogger instance.
        _context: Bound context dictionary.
    """

    def __init__(self, logger: StructuredLogger, context: dict[str, Any]) -> None:
        """Initialize bound logger.

        Args:
            logger: Parent StructuredLogger to delegate to.
            context: Context dictionary to include in all log calls.
        """
        self._logger = logger
        self._context = context

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log DEBUG message with bound context."""
        self._logger.debug(msg, *args, **{**self._context, **kwargs})

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log INFO message with bound context."""
        self._logger.info(msg, *args, **{**self._context, **kwargs})

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log WARNING message with bound context."""
        self._logger.warning(msg, *args, **{**self._context, **kwargs})

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log ERROR message with bound context."""
        self._logger.error(msg, *args, **{**self._context, **kwargs})

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log CRITICAL message with bound context."""
        self._logger.critical(msg, *args, **{**self._context, **kwargs})

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log ERROR message with exception info and bound context."""
        self._logger.exception(msg, *args, **{**self._context, **kwargs})

    def bind(self, **kwargs: Any) -> BoundLogger:
        """Create a new bound logger with additional context."""
        return BoundLogger(self._logger, {**self._context, **kwargs})


def get_current_context() -> dict[str, Any]:
    """Get the current log context from context variable or thread-local.

    Returns:
        Current context dictionary. Falls back to thread-local storage
        for non-async contexts. Returns empty dict if no context is set.
    """
    try:
        return _log_context.get()
    except LookupError:
        # Fall back to thread-local for non-async contexts
        return getattr(_thread_context, "context", {})


def set_context(**kwargs: Any) -> None:
    """Set values in the current log context.

    Args:
        **kwargs: Context key-value pairs to set.

    Returns:
        None. Context is updated in-place.
    """
    current = get_current_context().copy()
    current.update(kwargs)
    _log_context.set(current)
    _thread_context.context = current


def clear_context() -> None:
    """Clear the current log context.

    Returns:
        None. Both context variable and thread-local are reset to empty.
    """
    _log_context.set({})
    _thread_context.context = {}


@contextmanager
def log_context(**kwargs: Any) -> Generator[dict[str, Any], None, None]:
    """Context manager for scoped log context.

    All log calls within this context will include the specified
    parameters automatically.

    Args:
        **kwargs: Context to add for the scope

    Yields:
        The combined context dictionary

    Example:
        >>> with log_context(request_id="abc123", user="analyst"):
        ...     logger.info("Processing")  # Includes request_id and user
    """
    # Save current context
    old_context = get_current_context().copy()

    # Set new context
    new_context = {**old_context, **kwargs}
    _log_context.set(new_context)
    _thread_context.context = new_context

    try:
        yield new_context
    finally:
        # Restore old context
        _log_context.set(old_context)
        _thread_context.context = old_context


# Logger cache to avoid creating multiple instances
_loggers: dict[str, StructuredLogger] = {}
_loggers_lock = threading.Lock()


def get_structured_logger(name: str, *, redact_phi: bool = True) -> StructuredLogger:
    """Get or create a structured logger for the given name.

    Uses caching to ensure only one logger per name is created.

    Args:
        name: Logger name (typically __name__)
        redact_phi: Automatically redact PHI patterns

    Returns:
        StructuredLogger instance
    """
    with _loggers_lock:
        if name not in _loggers:
            _loggers[name] = StructuredLogger(name, redact_phi=redact_phi)
        return _loggers[name]


def configure_logging(
    *,
    level: str = "INFO",
    json_output: bool = False,
    verbose: bool = False,
    log_file: Path | None = None,
    redact_phi: bool = True,
) -> None:
    """Configure the logging system.

    This function configures both the base logging system and
    structured logging options.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Enable JSON-formatted output
        verbose: Enable verbose (DEBUG) logging
        log_file: Optional file path for JSON log output
        redact_phi: Enable PHI redaction in structured logs

    Example:
        >>> configure_logging(level="DEBUG", verbose=True)
        >>> configure_logging(json_output=True, log_file=Path("app.json.log"))
    """
    import logging as std_logging

    from scripts.utils.logging import setup_logger

    # Determine effective level
    effective_level = std_logging.DEBUG if verbose else getattr(std_logging, level)

    # Set up base logger
    setup_logger(
        name="reportalin-specialist",
        log_level=effective_level,
        simple_mode=not verbose,
    )

    # Configure JSON handler if requested
    if json_output:
        root_logger = std_logging.getLogger("reportalin-specialist")

        # Create JSON formatter
        json_formatter = JSONFormatter(
            include_timestamp=True,
            redact_phi=redact_phi,
        )

        # Add JSON file handler if specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = std_logging.FileHandler(log_file)
            file_handler.setFormatter(json_formatter)
            file_handler.setLevel(effective_level)
            root_logger.addHandler(file_handler)

        # Optionally add JSON console handler
        # (commented out to avoid duplicate output)
        # json_console = std_logging.StreamHandler(sys.stdout)
        # json_console.setFormatter(json_formatter)
        # root_logger.addHandler(json_console)


# Convenience function for importing
def setup_structured_logging(**kwargs: Any) -> None:
    """Alias for configure_logging for backwards compatibility.

    Args:
        **kwargs: All arguments are passed to configure_logging().

    Returns:
        None.
    """
    configure_logging(**kwargs)
