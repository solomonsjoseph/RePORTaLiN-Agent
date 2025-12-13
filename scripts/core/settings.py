"""Backward-compatible shim for scripts/core/settings.py.

DEPRECATED: Use reportalin.core.config instead.
This module re-exports all symbols from reportalin.core.config for backward compatibility.
"""
from reportalin.core.config import *  # noqa: F401, F403
