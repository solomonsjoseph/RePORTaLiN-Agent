"""Backward-compatible shim for scripts/core/structured_logging.py.

DEPRECATED: Use reportalin.core.logging instead.
This module re-exports all symbols from reportalin.core.logging for backward compatibility.
"""
from reportalin.core.logging import *  # noqa: F401, F403
