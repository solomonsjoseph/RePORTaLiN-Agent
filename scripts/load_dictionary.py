"""Backward-compatible shim for scripts/load_dictionary.py.

DEPRECATED: Use reportalin.data.load_dictionary instead.
This module re-exports all symbols from reportalin.data.load_dictionary for backward compatibility.
"""
from reportalin.data.load_dictionary import *  # noqa: F401, F403
