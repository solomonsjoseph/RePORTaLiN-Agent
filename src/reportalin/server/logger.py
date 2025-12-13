"""Backward-compatible re-export from core.logging.

This module re-exports all logging functionality from reportalin.core.logging.
Use reportalin.core.logging directly in new code.

DEPRECATED: This module exists for backward compatibility only.
            Prefer importing from reportalin.core.logging instead.
"""
from reportalin.core.logging import *  # noqa: F401, F403

__all__ = [
    "configure_logging",
    "get_logger",
    "bind_context",
    "clear_context",
    "get_request_id",
    "set_request_id",
    "add_request_id",
    "add_service_info",
    "filter_sensitive_data",
    "add_timestamp",
]
