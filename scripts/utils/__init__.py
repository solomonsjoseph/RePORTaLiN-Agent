#!/usr/bin/env python3
"""
RePORTaLiN-Specialist Utilities Package.

Logging and privacy compliance utilities.

Modules:
    - ``logging``: Centralized logging with custom SUCCESS level
    - ``country_regulations``: Country-specific privacy regulations (14 countries)

Usage:
    ::

        from scripts.utils import get_logger, success
        logger = get_logger()
        success("Processing complete!")
"""

from __future__ import annotations

from __version__ import __version__

from .logging import (
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
