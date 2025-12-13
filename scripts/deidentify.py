"""Backward-compatible shim for scripts/deidentify.py.

DEPRECATED: Use reportalin.data.deidentify instead.
This module re-exports all symbols from reportalin.data.deidentify for backward compatibility.
"""
from reportalin.data.deidentify import *  # noqa: F401, F403
