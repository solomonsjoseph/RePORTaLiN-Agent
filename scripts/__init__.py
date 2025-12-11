#!/usr/bin/env python3
"""
RePORTaLiN-Specialist Scripts Package.

Core data processing modules for clinical research data extraction and de-identification.

Modules:
    - ``load_dictionary``: Data dictionary processing
    - ``extract_data``: Excel to JSONL extraction
    - ``deidentify``: PHI/PII de-identification engine
    - ``core/``: Settings, structured logging, and log decryption
    - ``utils/``: Logging and country regulations

Usage:
    Basic pipeline::

        from scripts import load_study_dictionary, extract_excel_to_jsonl

        # Load data dictionary
        load_study_dictionary()

        # Extract dataset
        extract_excel_to_jsonl()

    With de-identification::

        from scripts.deidentify import deidentify_dataset, DeidentificationConfig

        config = DeidentificationConfig(countries=['IN', 'US'])
        deidentify_dataset(
            input_dir="results/dataset",
            output_dir="results/deidentified",
            config=config,
        )
"""

from __future__ import annotations

from __version__ import __version__

from .extract_data import extract_excel_to_jsonl
from .load_dictionary import load_study_dictionary, process_excel_file

__all__ = [
    "__version__",
    "extract_excel_to_jsonl",
    "load_study_dictionary",
    "process_excel_file",
]
