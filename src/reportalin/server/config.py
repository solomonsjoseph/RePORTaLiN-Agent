"""Backward-compatible re-export from core.config.

This module re-exports all configuration functionality from reportalin.core.config.
Use reportalin.core.config directly in new code.

DEPRECATED: This module exists for backward compatibility only.
            Prefer importing from reportalin.core.config instead.
"""
from reportalin.core.config import *  # noqa: F401, F403

__all__ = [
    "Environment",
    "LogLevel",
    "Settings",
    "get_settings",
    "reload_settings",
]
