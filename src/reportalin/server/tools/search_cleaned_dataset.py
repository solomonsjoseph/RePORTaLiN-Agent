"""Tool: Search the cleaned de-identified dataset for aggregate statistics.

SECURITY: Returns ONLY aggregates (counts, means, distributions).
NEVER returns individual patient records.

Use this to answer questions like:
- "What is the age distribution?"
- "How many participants are male vs female?"
- "What percentage have HIV?"

This tool queries ONLY the cleaned de-identified dataset (not original).
Per user requirements, we expose only de-identified data for privacy protection.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from reportalin.server.logger import get_logger
from reportalin.server.tools._analyzers import compute_variable_stats
from reportalin.server.tools._loaders import get_cleaned_dataset
from reportalin.server.tools._models import SearchCleanedDatasetInput

__all__ = ["search_cleaned_dataset"]

logger = get_logger(__name__)


async def search_cleaned_dataset(
    input: SearchCleanedDatasetInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Search the CLEANED de-identified dataset for aggregate statistics.

    SECURITY: Returns ONLY aggregates (counts, means, distributions).
    NEVER returns individual patient records.

    Use this to answer questions like:
    - "What is the age distribution?"
    - "How many participants are male vs female?"
    - "What percentage have HIV?"

    Args:
        input: Variable to analyze
        ctx: MCP context

    Returns:
        Aggregate statistics for the variable (counts, percentages, distributions)
    """
    await ctx.info(f"Searching cleaned dataset for: {input.variable}")

    try:
        dataset = get_cleaned_dataset()

        if not dataset:
            return {"error": "Cleaned dataset not available"}

        var_lower = input.variable.lower()
        results = {
            "variable_searched": input.variable,
            "dataset": "cleaned (deidentified)",
            "tables_analyzed": [],
            "aggregates": [],
        }

        for table_name, records in dataset.items():
            if (
                input.table_filter
                and input.table_filter.lower() not in table_name.lower()
            ):
                continue

            if not records:
                continue

            # Find matching variables in this table
            sample = records[0]
            matching_vars = [k for k in sample.keys() if var_lower in k.lower()]

            for var in matching_vars:
                stats = compute_variable_stats(records, var)
                stats["table"] = table_name
                results["aggregates"].append(stats)
                results["tables_analyzed"].append(table_name)

        results["tables_analyzed"] = list(set(results["tables_analyzed"]))
        results["total_matches"] = len(results["aggregates"])

        if not results["aggregates"]:
            return {
                "variable_searched": input.variable,
                "status": "not_found",
                "suggestion": "Use search_data_dictionary first to find exact variable names, "
                "or use combined_search for automatic variable discovery",
            }

        return results

    except Exception as e:
        logger.error(f"Cleaned dataset search failed: {e}")
        return {"error": str(e)}
