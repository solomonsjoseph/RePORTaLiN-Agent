"""Data loading utilities for MCP tools.

This module provides functions to load and cache data from:
- Data dictionary JSONL files
- Codelist definitions
- Cleaned and original datasets
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reportalin.core.logging import get_logger

__all__ = [
    "DATA_DICTIONARY_PATH",
    "CLEANED_DATA_PATH",
    "ORIGINAL_DATA_PATH",
    "load_data_dictionary",
    "load_codelists",
    "load_dataset",
    "get_data_dictionary",
    "get_codelists",
    "get_cleaned_dataset",
    "get_original_dataset",
]

# Initialize logger
logger = get_logger(__name__)

# =============================================================================
# Path Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DICTIONARY_PATH = PROJECT_ROOT / "results" / "data_dictionary_mappings"
CLEANED_DATA_PATH = PROJECT_ROOT / "results" / "deidentified" / "Indo-vap" / "cleaned"
ORIGINAL_DATA_PATH = PROJECT_ROOT / "results" / "deidentified" / "Indo-vap" / "original"


# =============================================================================
# Data Loading Functions
# =============================================================================


def load_data_dictionary() -> dict[str, list[dict]]:
    """Load all data dictionary JSONL files.

    Returns:
        Dictionary mapping table names to lists of field definition records.
        Empty dict if path doesn't exist or no files found.
    """
    all_data: dict[str, list[dict]] = {}

    if not DATA_DICTIONARY_PATH.exists():
        logger.warning(f"Data dictionary path not found: {DATA_DICTIONARY_PATH}")
        return all_data

    for jsonl_file in DATA_DICTIONARY_PATH.rglob("*.jsonl"):
        table_name = jsonl_file.stem
        records = []

        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            all_data[table_name] = records
        except Exception as e:
            logger.error(f"Error loading {jsonl_file}: {e}")

    return all_data


def load_codelists() -> dict[str, list[dict]]:
    """Load all codelist definitions.

    Returns:
        Dictionary mapping codelist names to lists of code/descriptor records.
        Empty dict if codelist path doesn't exist.
    """
    codelists: dict[str, list[dict]] = {}
    codelist_path = DATA_DICTIONARY_PATH / "Codelists"

    if not codelist_path.exists():
        return codelists

    for jsonl_file in codelist_path.glob("*.jsonl"):
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        # Handle both field name formats
                        codelist_name = (
                            record.get("Codelist")
                            or record.get("New codelists")
                            or "UNKNOWN"
                        )
                        if codelist_name not in codelists:
                            codelists[codelist_name] = []
                        codelists[codelist_name].append(record)
        except Exception as e:
            logger.error(f"Error loading codelist {jsonl_file}: {e}")

    return codelists


def load_dataset(path: Path) -> dict[str, list[dict]]:
    """Load dataset from a directory of JSONL files.

    Args:
        path: Directory path containing JSONL files.

    Returns:
        Dictionary mapping table names (file stems) to lists of records.
        Empty dict if path doesn't exist.
    """
    dataset: dict[str, list[dict]] = {}

    if not path.exists():
        logger.warning(f"Dataset path not found: {path}")
        return dataset

    for jsonl_file in path.glob("*.jsonl"):
        table_name = jsonl_file.stem
        records = []

        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            dataset[table_name] = records
        except Exception as e:
            logger.error(f"Error loading dataset {jsonl_file}: {e}")

    return dataset


# =============================================================================
# Cache
# =============================================================================

_dict_cache: dict[str, list[dict]] | None = None
_codelist_cache: dict[str, list[dict]] | None = None
_cleaned_cache: dict[str, list[dict]] | None = None
_original_cache: dict[str, list[dict]] | None = None


def get_data_dictionary() -> dict[str, list[dict]]:
    """Get cached data dictionary.

    Returns:
        Dictionary mapping table names to field definitions.
    """
    global _dict_cache
    if _dict_cache is None:
        _dict_cache = load_data_dictionary()
    return _dict_cache


def get_codelists() -> dict[str, list[dict]]:
    """Get cached codelists.

    Returns:
        Dictionary mapping codelist names to code/descriptor records.
    """
    global _codelist_cache
    if _codelist_cache is None:
        _codelist_cache = load_codelists()
    return _codelist_cache


def get_cleaned_dataset() -> dict[str, list[dict]]:
    """Get cached cleaned dataset.

    Returns:
        Dictionary mapping table names to de-identified records.
    """
    global _cleaned_cache
    if _cleaned_cache is None:
        _cleaned_cache = load_dataset(CLEANED_DATA_PATH)
    return _cleaned_cache


def get_original_dataset() -> dict[str, list[dict]]:
    """Get cached original dataset.

    Returns:
        Dictionary mapping table names to original de-identified records.
    """
    global _original_cache
    if _original_cache is None:
        _original_cache = load_dataset(ORIGINAL_DATA_PATH)
    return _original_cache
