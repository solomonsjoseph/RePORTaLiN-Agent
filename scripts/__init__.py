"""Backward-compatible shim for scripts package.

DEPRECATED: Use reportalin.data instead.
This module re-exports symbols from reportalin.data for backward compatibility.
"""
from reportalin.data.load_dictionary import load_study_dictionary, process_excel_file
from reportalin.data.extract import extract_excel_to_jsonl
from reportalin import __version__

__all__ = [
    "__version__",
    "extract_excel_to_jsonl",
    "load_study_dictionary",
    "process_excel_file",
]
