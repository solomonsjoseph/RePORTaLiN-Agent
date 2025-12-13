"""Backward-compatible shim for scripts/utils package.

DEPRECATED: Use reportalin.data.utils instead.
This module re-exports symbols from reportalin.data.utils for backward compatibility.
"""
from reportalin import __version__

from reportalin.data.utils.logging import (
    critical,
    debug,
    error,
    get_log_file_path,
    get_logger,
    info,
    setup_logger,
    success,
    warning,
)

__all__ = [
    "__version__",
    "critical",
    "debug",
    "error",
    "get_log_file_path",
    "get_logger",
    "info",
    "setup_logger",
    "success",
    "warning",
]
