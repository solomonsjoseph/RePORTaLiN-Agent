# config.py
"""
RePORTaLiN-Specialist Configuration Module.

Centralized configuration management with dynamic dataset detection,
automatic path resolution, and flexible logging configuration.

This module provides backward compatibility with the legacy configuration
system while delegating to the new Pydantic-based settings system.

Module:
    config - Configuration management for RePORTaLiN-Specialist project

New Architecture:
    For new code, prefer using the centralized settings:
    
        from scripts.core import get_settings
        settings = get_settings()
        
    This module is maintained for backward compatibility with existing code.

See Also:
    - scripts/core/settings.py - Pydantic-based settings management
    - scripts/core/structured_logging.py - Structured logging configuration
"""

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Safe version import with fallback
try:
    from __version__ import __version__
except ImportError:
    __version__ = "unknown"

# =============================================================================
# Try to use new Pydantic settings, fall back to legacy if unavailable
# =============================================================================
_USE_NEW_SETTINGS = False

try:
    from scripts.core.settings import get_settings as _get_pydantic_settings
    _USE_NEW_SETTINGS = True
except ImportError:
    # Pydantic settings not available (missing pydantic-settings)
    # Fall back to legacy configuration
    pass

# Constants
DEFAULT_DATASET_NAME = "RePORTaLiN_sample"
DATASET_SUFFIXES = ("_csv_files", "_files")

# Explicitly define public API
__all__ = [
    # Path constants
    "ROOT_DIR",
    "DATA_DIR",
    "RESULTS_DIR",
    "DATASET_BASE_DIR",
    "DATASET_FOLDER_NAME",
    "DATASET_DIR",
    "DATASET_NAME",
    "CLEAN_DATASET_DIR",
    "DICTIONARY_EXCEL_FILE",
    "DICTIONARY_JSON_OUTPUT_DIR",
    # Configuration constants
    "LOG_LEVEL",
    "LOG_NAME",
    "DEFAULT_DATASET_NAME",
    "DATASET_SUFFIXES",
    # Public functions
    "ensure_directories",
    "validate_config",
    "get_settings",
    # Helper functions (used internally during module initialization)
    "get_dataset_folder",
    "normalize_dataset_name",
]


# =============================================================================
# Settings Access (New API)
# =============================================================================
def get_settings():
    """Get the centralized settings object.
    
    Returns:
        Settings object from scripts.core.settings if available,
        or a compatibility wrapper for legacy config.
        
    Example:
        >>> settings = get_settings()
        >>> print(settings.data_dir)
    """
    if _USE_NEW_SETTINGS:
        return _get_pydantic_settings()
    else:
        # Return a simple namespace with legacy config values
        class LegacySettings:
            """Compatibility wrapper for legacy configuration."""
            data_dir = Path(DATA_DIR)
            results_dir = Path(RESULTS_DIR)
            dataset_dir = Path(DATASET_DIR)
            dataset_name = DATASET_NAME
            log_level = LOG_LEVEL
            log_name = LOG_NAME
            
            @property
            def logging(self):
                """Compatibility property for logging settings."""
                class LoggingSettings:
                    level = "INFO"
                    verbose = LOG_LEVEL == logging.DEBUG
                return LoggingSettings()
        
        return LegacySettings()


# =============================================================================
# Project paths
# =============================================================================
ROOT_DIR = (
    os.path.dirname(os.path.abspath(__file__))
    if "__file__" in globals()
    else os.getcwd()
)
DATA_DIR = os.path.join(ROOT_DIR, "data")
RESULTS_DIR = os.path.join(ROOT_DIR, "results")
DATASET_BASE_DIR = os.path.join(DATA_DIR, "dataset")


def get_dataset_folder() -> str | None:
    """
    Detect first dataset folder in data/dataset/, excluding hidden folders.

    Returns:
        Name of the first dataset folder found, or None if none exists

    Note:
        Folders starting with '.' are excluded as they are typically hidden.
        Errors during directory listing are silently handled to avoid issues
        during module initialization (before logging is configured).
    """
    if not os.path.exists(DATASET_BASE_DIR):
        return None

    try:
        folders = [
            f
            for f in os.listdir(DATASET_BASE_DIR)
            if os.path.isdir(os.path.join(DATASET_BASE_DIR, f))
            and not f.startswith(".")
        ]
        if not folders:
            return None
        return sorted(folders)[0]
    except (OSError, PermissionError) as e:
        # Silently return None on errors during config initialization
        # Logging will be available later after logger is set up
        # Store error for later reporting if needed
        import sys

        print(f"Warning: Error accessing dataset directory: {e}", file=sys.stderr)
        return None


def normalize_dataset_name(folder_name: str | None) -> str:
    """
    Normalize dataset folder name by removing common suffixes.

    Args:
        folder_name: The dataset folder name to normalize

    Returns:
        Normalized dataset name

    Note:
        Removes the longest matching suffix to ensure correct normalization
        regardless of suffix ordering (e.g., '_csv_files' before '_files').
        Whitespace is stripped before suffix removal for consistent behavior.
    """
    if not folder_name:
        return DEFAULT_DATASET_NAME

    # Strip whitespace first to ensure suffix detection works correctly
    name = folder_name.strip()
    if not name:
        return DEFAULT_DATASET_NAME

    # Find and remove the longest matching suffix
    matching_suffixes = [s for s in DATASET_SUFFIXES if name.endswith(s)]
    if matching_suffixes:
        # Remove the longest suffix to handle cases like '_csv_files' vs '_files'
        longest_suffix = max(matching_suffixes, key=len)
        name = name[: -len(longest_suffix)]

    # Strip again after suffix removal
    name = name.strip()
    return name if name else DEFAULT_DATASET_NAME


# Dataset configuration
DATASET_FOLDER_NAME = get_dataset_folder()
# Construct dataset directory path with fallback
if DATASET_FOLDER_NAME:
    DATASET_DIR = os.path.join(DATASET_BASE_DIR, DATASET_FOLDER_NAME)
else:
    # Use default as fallback if no dataset folder found
    DATASET_DIR = os.path.join(DATASET_BASE_DIR, DEFAULT_DATASET_NAME)
DATASET_NAME = normalize_dataset_name(DATASET_FOLDER_NAME)
CLEAN_DATASET_DIR = os.path.join(RESULTS_DIR, "dataset", DATASET_NAME)

# Data dictionary paths
DICTIONARY_EXCEL_FILE = os.path.join(
    DATA_DIR,
    "data_dictionary_and_mapping_specifications",
    "RePORT_DEB_to_Tables_mapping.xlsx",
)
DICTIONARY_JSON_OUTPUT_DIR = os.path.join(RESULTS_DIR, "data_dictionary_mappings")

# Logging configuration
LOG_LEVEL = logging.INFO
LOG_NAME = "reportalin-specialist"


# Utility functions
def ensure_directories() -> None:
    """Create necessary directories if they don't exist."""
    directories = [RESULTS_DIR, CLEAN_DATASET_DIR, DICTIONARY_JSON_OUTPUT_DIR]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def validate_config() -> list[str]:
    """
    Validate configuration and return list of warnings.

    Returns:
        List of warning messages for missing or invalid configuration
    """
    warnings = []

    try:
        if not os.path.exists(DATA_DIR):
            warnings.append(f"Data directory not found: {DATA_DIR}")

        if not os.path.exists(DATASET_DIR):
            warnings.append(f"Dataset directory not found: {DATASET_DIR}")

        if not os.path.exists(DICTIONARY_EXCEL_FILE):
            warnings.append(f"Data dictionary file not found: {DICTIONARY_EXCEL_FILE}")
    except (OSError, PermissionError) as e:
        warnings.append(f"Error validating configuration: {e}")

    return warnings
