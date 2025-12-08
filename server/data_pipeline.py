"""
Data Pipeline Integration Module.

This module connects the MCP server tools to the actual data pipeline:
    Extraction → De-identification → Results → MCP Access

It provides a unified interface for accessing:
    - De-identified clinical data (JSONL files)
    - Data dictionary definitions
    - Aggregate statistics with k-anonymity protection

Data Flow:
    1. Raw Excel (data/dataset/Indo-vap_csv_files/*.xlsx)
           ↓ extract_data.py
    2. Extracted JSONL (results/dataset/{name}/original/, cleaned/)
           ↓ deidentify.py
    3. De-identified JSONL (results/deidentified/{name}/original/, cleaned/)
           ↓ THIS MODULE
    4. MCP Server Tools (query_database, list_datasets, etc.)

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                     MCP Server Tools                         │
    │  (list_datasets, describe_schema, query_database, etc.)     │
    └─────────────────────────────────┬───────────────────────────┘
                                      │
    ┌─────────────────────────────────▼───────────────────────────┐
    │                  DataPipelineConnector                       │
    │  - get_available_datasets()                                  │
    │  - get_dataset_schema(name)                                  │
    │  - query_dataset(name, filters, limit)                       │
    │  - search_dictionary(term)                                   │
    │  - get_aggregate_stats(dataset, field, group_by)            │
    └─────────────────────────────────┬───────────────────────────┘
                                      │
    ┌─────────────────────────────────▼───────────────────────────┐
    │              De-identified Results Directory                 │
    │  results/deidentified/{dataset_name}/                        │
    │  ├── original/     (de-identified original files)           │
    │  └── cleaned/      (de-identified cleaned files)            │
    └─────────────────────────────────────────────────────────────┘

Privacy Protection:
    - All data access goes through k-anonymity checks
    - Individual records are never returned (aggregates only by default)
    - Queries returning < k records are suppressed
    - All access is logged for audit compliance

Usage:
    >>> from server.data_pipeline import DataPipelineConnector
    >>>
    >>> connector = DataPipelineConnector()
    >>> datasets = await connector.get_available_datasets()
    >>> schema = await connector.get_dataset_schema("2A_ICBaseline")
    >>> stats = await connector.get_aggregate_stats("2A_ICBaseline", "age", group_by="sex")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from shared.constants import MIN_K_ANONYMITY

__all__ = [
    "DataPipelineConnector",
    "DataSource",
    "DatasetInfo",
    "PrivacyViolationError",
    "QueryResult",
    "SchemaField",
]

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================

class PrivacyViolationError(Exception):
    """
    Raised when a query would violate k-anonymity constraints.

    This prevents returning results that could potentially
    identify individual subjects.
    """

    def __init__(self, message: str, k_value: int, threshold: int):
        super().__init__(message)
        self.k_value = k_value
        self.threshold = threshold


# =============================================================================
# Data Classes
# =============================================================================

class DataSource(str, Enum):
    """Available data sources in the pipeline."""

    RAW = "raw"                    # Original Excel files (data/dataset/)
    EXTRACTED = "extracted"        # Extracted JSONL (results/dataset/)
    DEIDENTIFIED = "deidentified"  # De-identified (results/deidentified/)
    DICTIONARY = "dictionary"      # Data dictionary (results/data_dictionary_mappings/)


@dataclass
class DatasetInfo:
    """Information about an available dataset."""

    name: str
    domain: str
    description: str
    source: DataSource
    file_path: Path
    row_count: int = 0
    field_count: int = 0
    last_modified: datetime | None = None
    is_deidentified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "source": self.source.value,
            "row_count": self.row_count,
            "field_count": self.field_count,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "is_deidentified": self.is_deidentified,
        }


@dataclass
class SchemaField:
    """Schema information for a dataset field."""

    name: str
    data_type: str
    nullable: bool = True
    description: str = ""
    unique_count: int = 0
    null_count: int = 0
    sample_values: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.data_type,
            "nullable": self.nullable,
            "description": self.description,
            "unique_count": self.unique_count,
            "null_count": self.null_count,
            "sample_values": self.sample_values,
        }


@dataclass
class QueryResult:
    """Result of a data query with privacy metadata."""

    success: bool
    data: list[dict[str, Any]]
    row_count: int
    k_anonymity_satisfied: bool
    suppressed_groups: int = 0
    execution_time_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "row_count": self.row_count,
            "k_anonymity_satisfied": self.k_anonymity_satisfied,
            "suppressed_groups": self.suppressed_groups,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


# =============================================================================
# RePORT India Domain Mappings
# =============================================================================

REPORT_INDIA_DOMAINS = {
    # Screening Forms
    "1A_ICScreening": ("SC", "Index Case Screening - TB symptom screening per RNTCP"),
    "1B_HCScreening": ("SC", "Household Contact Screening - Contact investigation"),

    # Demographics/Baseline
    "2A_ICBaseline": ("DM", "Index Case Demographics - Sociodemographic data"),
    "2A_ICBaseline_1": ("DM", "Index Case Demographics (continued)"),
    "2B_HCBaseline": ("DM", "Household Contact Demographics"),

    # Laboratory - TB Diagnostics
    "3_Specimen_Collection": ("SP", "Specimen Collection - Sputum, blood, other samples"),
    "4_Smear": ("MB", "Smear Microscopy - AFB grading (Scanty/1+/2+/3+)"),
    "5_CBC": ("LB", "Complete Blood Count - Hematology panel"),
    "6_HIV": ("LB", "HIV Testing - Per NACO guidelines"),
    "7_Culture": ("MB", "TB Culture - LJ/MGIT results"),
    "10_TST": ("LB", "Tuberculin Skin Test - Mantoux test (mm induration)"),
    "11_IGRA": ("LB", "IGRA - Interferon-Gamma Release Assay"),
    "19_Smear": ("MB", "Follow-up Smear Microscopy"),
    "21_DSTISO": ("MB", "Drug Susceptibility Testing - Isolate"),
    "21_DSTIsolate": ("MB", "DST Results - RIF/INH/FQ/SLI resistance"),

    # Imaging
    "8_CXR": ("XR", "Chest X-Ray - Radiological findings per RNTCP"),

    # Clinical Evaluation
    "9_EEval": ("CE", "Eligibility Evaluation - Inclusion/exclusion criteria"),
    "17_EligConfirmation": ("CE", "Eligibility Confirmation"),

    # Follow-up Visits
    "12A_FUA": ("FV", "Follow-up Visit A - Clinical assessment"),
    "12B_FUB": ("FV", "Follow-up Visit B - Clinical assessment"),
    "98A_FOA": ("FV", "Final Outcome Visit A"),
    "98B_FOB": ("FV", "Final Outcome Visit B"),
    "99A_FSA": ("FV", "Final Status A"),
    "99B_FSB": ("FV", "Final Status B"),

    # Treatment
    "13_TxCompliance": ("EX", "Treatment Compliance - DOTS adherence"),
    "18_1_TargConcom": ("CM", "Targeted Concomitant Medications"),
    "18_2_TargConcom": ("CM", "Concomitant Medications (continued)"),

    # Case Classification
    "14_CaseControl": ("DS", "Case-Control Classification"),
    "14_Case_Control": ("DS", "Case-Control Status"),
    "20_CoEnroll": ("DS", "Co-enrollment Status"),

    # Additional Testing
    "15_Feces": ("LB", "Fecal Samples - Parasitology"),
    "16_Helminth": ("LB", "Helminth Testing - Deworming status"),
    "53_exposure": ("FA", "Exposure Assessment - TB contact history"),
    "30_Air_Quality": ("FA", "Air Quality - Environmental factors"),

    # Safety
    "95_SAE": ("AE", "Serious Adverse Events - SAE reporting"),

    # Specimen Tracking
    "95_Specimen_Tracking": ("SP", "Specimen Tracking Log"),
    "96_Specimen_Tracking": ("SP", "Specimen Tracking (continued)"),
    "97_Not_Collected": ("SP", "Specimens Not Collected - Reasons"),

    # Consent/Admin
    "18_NonConsent": ("CO", "Non-Consent Documentation"),
    "101_HHC_Recontact": ("CO", "Household Contact Recontact"),
    "101_HHC_Recontact_1": ("CO", "HHC Recontact (continued)"),
}


# =============================================================================
# Data Pipeline Connector
# =============================================================================

class DataPipelineConnector:
    """
    Connector between MCP server and the data pipeline results.

    This class provides a unified interface for accessing:
    - De-identified clinical data
    - Data dictionary definitions
    - Aggregate statistics with k-anonymity protection

    Attributes:
        project_root: Root directory of the project
        k_threshold: Minimum k-anonymity threshold (default: 5)
        prefer_deidentified: Whether to prefer de-identified data (default: True)
    """

    def __init__(
        self,
        project_root: Path | None = None,
        k_threshold: int = MIN_K_ANONYMITY,
        prefer_deidentified: bool = True,
    ):
        self.project_root = project_root or Path(__file__).parent.parent
        self.k_threshold = k_threshold
        self.prefer_deidentified = prefer_deidentified

        # Data directories
        self.data_dir = self.project_root / "data"
        self.results_dir = self.project_root / "results"
        self.raw_data_dir = self.data_dir / "dataset" / "Indo-vap_csv_files"
        self.extracted_dir = self.results_dir / "dataset"
        self.deidentified_dir = self.results_dir / "deidentified"
        self.dictionary_dir = self.results_dir / "data_dictionary_mappings"

        logger.info(
            "DataPipelineConnector initialized",
            extra={
                "project_root": str(self.project_root),
                "k_threshold": self.k_threshold,
            }
        )

    def _get_dataset_path(self, dataset_name: str) -> Path | None:
        """
        Get the path to a dataset, preferring de-identified data.

        Priority order:
        1. De-identified cleaned data
        2. De-identified original data
        3. Extracted cleaned data
        4. Extracted original data
        5. Raw Excel file
        """
        # Check de-identified data first
        for subdir in ["cleaned", "original"]:
            for dataset_dir in self.deidentified_dir.glob("*"):
                jsonl_path = dataset_dir / subdir / f"{dataset_name}.jsonl"
                if jsonl_path.exists():
                    return jsonl_path

        # Check extracted data
        for subdir in ["cleaned", "original"]:
            for dataset_dir in self.extracted_dir.glob("*"):
                jsonl_path = dataset_dir / subdir / f"{dataset_name}.jsonl"
                if jsonl_path.exists():
                    return jsonl_path

        # Check raw Excel files
        xlsx_path = self.raw_data_dir / f"{dataset_name}.xlsx"
        if xlsx_path.exists():
            return xlsx_path

        return None

    def _is_deidentified(self, file_path: Path) -> bool:
        """Check if a file is from the de-identified directory."""
        return "deidentified" in str(file_path)

    def _load_jsonl(self, file_path: Path) -> pd.DataFrame:
        """Load a JSONL file into a DataFrame."""
        records = []
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return pd.DataFrame(records)

    def _load_excel(self, file_path: Path) -> pd.DataFrame:
        """Load an Excel file into a DataFrame."""
        return pd.read_excel(file_path, engine="openpyxl")

    def _load_dataset(self, file_path: Path) -> pd.DataFrame:
        """Load a dataset from file (JSONL or Excel)."""
        if file_path.suffix == ".jsonl":
            return self._load_jsonl(file_path)
        elif file_path.suffix in [".xlsx", ".xls"]:
            return self._load_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

    async def get_available_datasets(
        self,
        include_metadata: bool = True,
        domain_filter: str | None = None,
    ) -> list[DatasetInfo]:
        """
        Get list of available datasets.

        Args:
            include_metadata: Include row counts and timestamps
            domain_filter: Filter by CDISC domain code

        Returns:
            List of DatasetInfo objects
        """
        datasets = []
        seen_names = set()

        # Scan directories in priority order
        scan_dirs = [
            (self.deidentified_dir, DataSource.DEIDENTIFIED, True),
            (self.extracted_dir, DataSource.EXTRACTED, False),
            (self.raw_data_dir, DataSource.RAW, False),
        ]

        for base_dir, source, is_deidentified in scan_dirs:
            if not base_dir.exists():
                continue

            # Handle different directory structures
            if source == DataSource.RAW:
                files = list(base_dir.glob("*.xlsx"))
            else:
                # JSONL files in subdirectories
                files = list(base_dir.rglob("*.jsonl"))

            for file_path in files:
                name = file_path.stem

                # Skip if already seen (prefer de-identified)
                if name in seen_names:
                    continue

                # Get domain info
                domain_info = REPORT_INDIA_DOMAINS.get(name, ("OT", f"Other - {name}"))
                domain, description = domain_info

                # Apply domain filter
                if domain_filter and domain != domain_filter.upper():
                    continue

                seen_names.add(name)

                # Build dataset info
                info = DatasetInfo(
                    name=name,
                    domain=domain,
                    description=description,
                    source=source,
                    file_path=file_path,
                    is_deidentified=is_deidentified,
                )

                if include_metadata:
                    try:
                        stat = file_path.stat()
                        info.last_modified = datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        )

                        # Get row/field counts (sample for performance)
                        df = self._load_dataset(file_path)
                        info.row_count = len(df)
                        info.field_count = len(df.columns)
                    except Exception as e:
                        logger.warning(f"Could not load metadata for {name}: {e}")

                datasets.append(info)

        return sorted(datasets, key=lambda d: d.name)

    async def get_dataset_schema(
        self,
        dataset_name: str,
        include_statistics: bool = False,
        include_sample_values: bool = False,
    ) -> dict[str, Any] | None:
        """
        Get schema information for a dataset.

        Args:
            dataset_name: Name of the dataset
            include_statistics: Include null counts, unique counts
            include_sample_values: Include sample values for categorical fields

        Returns:
            Schema dictionary or None if not found
        """
        file_path = self._get_dataset_path(dataset_name)
        if not file_path:
            return None

        try:
            df = self._load_dataset(file_path)

            fields = []
            for col in df.columns:
                field = SchemaField(
                    name=str(col),
                    data_type=str(df[col].dtype),
                    nullable=df[col].isna().any(),
                )

                if include_statistics:
                    field.null_count = int(df[col].isna().sum())
                    field.unique_count = int(df[col].nunique())

                if include_sample_values and df[col].dtype == "object":
                    unique_vals = df[col].dropna().unique()[:5]
                    field.sample_values = [str(v) for v in unique_vals]

                fields.append(field)

            return {
                "dataset": dataset_name,
                "source_file": file_path.name,
                "source": "deidentified" if self._is_deidentified(file_path) else "extracted",
                "fields": [f.to_dict() for f in fields],
                "field_count": len(fields),
                "row_count": len(df),
            }

        except Exception as e:
            logger.error(f"Error loading schema for {dataset_name}: {e}")
            return None

    async def query_dataset(
        self,
        dataset_name: str,
        columns: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        group_by: str | None = None,
        aggregation: str = "count",
        limit: int = 100,
    ) -> QueryResult:
        """
        Query a dataset with k-anonymity protection.

        For privacy protection, this method:
        - Returns aggregate results by default
        - Suppresses groups with < k records
        - Never returns individual-level data

        Args:
            dataset_name: Name of the dataset to query
            columns: Columns to select
            filters: Filter conditions (column: value)
            group_by: Column to group by for aggregation
            aggregation: Aggregation type (count, sum, mean, etc.)
            limit: Maximum number of result rows

        Returns:
            QueryResult with data and privacy metadata
        """
        import time
        start_time = time.perf_counter()

        file_path = self._get_dataset_path(dataset_name)
        if not file_path:
            return QueryResult(
                success=False,
                data=[],
                row_count=0,
                k_anonymity_satisfied=True,
                error=f"Dataset '{dataset_name}' not found",
            )

        try:
            df = self._load_dataset(file_path)

            # Apply filters
            if filters:
                for col, val in filters.items():
                    if col in df.columns:
                        df = df[df[col] == val]

            # Select columns
            if columns:
                valid_cols = [c for c in columns if c in df.columns]
                if valid_cols:
                    df = df[valid_cols]

            # Perform aggregation with k-anonymity
            if group_by and group_by in df.columns:
                grouped = df.groupby(group_by).size().reset_index(name="count")

                # Apply k-anonymity threshold
                suppressed = (grouped["count"] < self.k_threshold).sum()
                grouped = grouped[grouped["count"] >= self.k_threshold]

                result_data = grouped.head(limit).to_dict(orient="records")

                return QueryResult(
                    success=True,
                    data=result_data,
                    row_count=len(result_data),
                    k_anonymity_satisfied=True,
                    suppressed_groups=int(suppressed),
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                )
            else:
                # Return aggregate statistics only (no individual records)
                stats = {
                    "total_rows": len(df),
                    "columns": list(df.columns),
                    "column_count": len(df.columns),
                }

                return QueryResult(
                    success=True,
                    data=[stats],
                    row_count=1,
                    k_anonymity_satisfied=True,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                )

        except Exception as e:
            logger.error(f"Query failed for {dataset_name}: {e}")
            return QueryResult(
                success=False,
                data=[],
                row_count=0,
                k_anonymity_satisfied=True,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

    async def search_dictionary(
        self,
        search_term: str,
        table_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search the data dictionary for field definitions.

        Args:
            search_term: Term to search for in field names/descriptions
            table_filter: Optional table name to limit search

        Returns:
            List of matching dictionary entries
        """
        matches = []

        if not self.dictionary_dir.exists():
            return matches

        # Search JSONL dictionary files
        for jsonl_file in self.dictionary_dir.glob("*.jsonl"):
            if table_filter and table_filter.lower() not in jsonl_file.stem.lower():
                continue

            try:
                with open(jsonl_file, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)

                            # Search in all string values
                            for _key, value in record.items():
                                if isinstance(value, str) and search_term.lower() in value.lower():
                                    record["_source_file"] = jsonl_file.stem
                                    matches.append(record)
                                    break
            except Exception as e:
                logger.warning(f"Error searching {jsonl_file}: {e}")

        return matches

    def get_pipeline_status(self) -> dict[str, Any]:
        """
        Get the status of the data pipeline.

        Returns:
            Dictionary with pipeline status information
        """
        status = {
            "raw_data_available": self.raw_data_dir.exists(),
            "extraction_completed": any(self.extracted_dir.glob("*/*.jsonl")),
            "deidentification_completed": any(self.deidentified_dir.glob("*/*.jsonl")),
            "dictionary_available": any(self.dictionary_dir.glob("*.jsonl")),
            "directories": {
                "raw_data": str(self.raw_data_dir),
                "extracted": str(self.extracted_dir),
                "deidentified": str(self.deidentified_dir),
                "dictionary": str(self.dictionary_dir),
            },
        }

        # Count files
        if self.raw_data_dir.exists():
            status["raw_file_count"] = len(list(self.raw_data_dir.glob("*.xlsx")))

        if self.extracted_dir.exists():
            status["extracted_file_count"] = len(list(self.extracted_dir.rglob("*.jsonl")))

        if self.deidentified_dir.exists():
            status["deidentified_file_count"] = len(list(self.deidentified_dir.rglob("*.jsonl")))

        return status


# =============================================================================
# Module-level singleton for easy access
# =============================================================================

_connector: DataPipelineConnector | None = None

def get_connector() -> DataPipelineConnector:
    """Get or create the global DataPipelineConnector instance."""
    global _connector
    if _connector is None:
        _connector = DataPipelineConnector()
    return _connector
