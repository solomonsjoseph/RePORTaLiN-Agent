"""Statistical analysis utilities for MCP tools.

This module provides functions to compute aggregate statistics on clinical data
while ensuring privacy (no individual records exposed).
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

__all__ = [
    "compute_variable_stats",
    "compute_histogram",
    "find_variable_in_dataset",
]


def compute_variable_stats(records: list[dict], variable: str) -> dict[str, Any]:
    """
    Compute SAFE aggregate statistics for a variable.

    Returns counts, distributions - NEVER raw values.

    Args:
        records: List of data records to analyze.
        variable: Variable/field name to compute statistics for.

    Returns:
        Dictionary with aggregate statistics including type, counts,
        and either numeric statistics or categorical value counts.
    """
    values = [r.get(variable) for r in records if r.get(variable) is not None]

    if not values:
        return {"status": "no_data", "variable": variable}

    # Determine type
    numeric_values = []
    categorical_values = []

    for v in values:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            numeric_values.append(v)
        else:
            categorical_values.append(str(v))

    result = {
        "variable": variable,
        "total_records": len(records),
        "non_null_count": len(values),
        "null_count": len(records) - len(values),
        "null_percentage": round((len(records) - len(values)) / len(records) * 100, 1),
    }

    if numeric_values and len(numeric_values) > len(categorical_values):
        # Numeric variable - return statistics, NOT raw values
        result["type"] = "numeric"
        result["statistics"] = {
            "min": round(min(numeric_values), 2),
            "max": round(max(numeric_values), 2),
            "mean": round(statistics.mean(numeric_values), 2),
            "median": round(statistics.median(numeric_values), 2),
        }
        if len(numeric_values) > 1:
            result["statistics"]["std_dev"] = round(statistics.stdev(numeric_values), 2)

        # Provide distribution bins, NOT raw values
        result["distribution"] = compute_histogram(numeric_values)
    else:
        # Categorical variable - return value counts
        result["type"] = "categorical"
        counts = Counter(categorical_values)

        # Return top values with counts (safe aggregate)
        result["value_counts"] = [
            {"value": k, "count": v, "percentage": round(v / len(values) * 100, 1)}
            for k, v in counts.most_common(20)  # Limit to top 20
        ]
        result["unique_values"] = len(counts)

    return result


def compute_histogram(values: list[float], bins: int = 10) -> list[dict]:
    """Compute histogram bins for numeric data.

    Args:
        values: List of numeric values to bin.
        bins: Number of histogram bins (default: 10).

    Returns:
        List of dicts with 'range' and 'count' keys for each bin.
    """
    if not values:
        return []

    min_val, max_val = min(values), max(values)
    if min_val == max_val:
        return [{"range": f"{min_val}", "count": len(values)}]

    bin_width = (max_val - min_val) / bins
    histogram = []

    for i in range(bins):
        bin_start = min_val + i * bin_width
        bin_end = bin_start + bin_width
        count = sum(1 for v in values if bin_start <= v < bin_end)
        if i == bins - 1:  # Last bin includes max
            count = sum(1 for v in values if bin_start <= v <= bin_end)

        histogram.append(
            {"range": f"{round(bin_start, 1)}-{round(bin_end, 1)}", "count": count}
        )

    return histogram


def find_variable_in_dataset(
    dataset: dict[str, list[dict]], variable: str
) -> list[tuple[str, str, list[dict]]]:
    """Find which tables contain a variable.

    Args:
        dataset: Dataset dictionary mapping table names to records.
        variable: Variable name to search for (case-insensitive partial match).

    Returns:
        List of tuples containing (table_name, matched_key, records) for each match.
    """
    matches = []
    var_lower = variable.lower()

    for table_name, records in dataset.items():
        if records:
            # Check if variable exists in this table
            sample = records[0]
            for key in sample.keys():
                if var_lower in key.lower():
                    matches.append((table_name, key, records))
                    break

    return matches
