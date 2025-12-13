"""Backward-compatible shim for scripts/extract_data.py.

DEPRECATED: Use reportalin.data.extract instead.
This module re-exports all symbols from reportalin.data.extract for backward compatibility.
"""
from reportalin.data.extract import *  # noqa: F401, F403
