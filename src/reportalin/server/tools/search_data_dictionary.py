"""Tool: Search data dictionary for variable definitions and metadata.

This tool searches ONLY for variable definitions and metadata - NO statistics.

USE THIS TOOL ONLY WHEN:
- User specifically asks "what variables exist for X?"
- User asks "what does variable Y mean?"
- User wants to know field names, data types, or codelist values
- User needs ONLY metadata without any statistics

DO NOT USE THIS TOOL WHEN:
- User asks for counts, distributions, or statistics (use combined_search instead)
- User asks "how many patients have X?" (use combined_search instead)
- User asks any analytical question (use combined_search instead)

This merges functionality from:
- Original search_data_dictionary (metadata lookup)
- variable_details (comprehensive variable information)
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from reportalin.server.logger import get_logger
from reportalin.server.tools._loaders import get_codelists, get_data_dictionary
from reportalin.server.tools._models import SearchDataDictionaryInput

__all__ = ["search_data_dictionary"]

logger = get_logger(__name__)


async def search_data_dictionary(
    input: SearchDataDictionaryInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Search ONLY for variable definitions and metadata - NO statistics.

    USE THIS TOOL ONLY WHEN:
    - User specifically asks "what variables exist for X?"
    - User asks "what does variable Y mean?"
    - User wants to know field names, data types, or codelist values
    - User needs ONLY metadata without any statistics

    DO NOT USE THIS TOOL WHEN:
    - User asks for counts, distributions, or statistics (use combined_search instead)
    - User asks "how many patients have X?" (use combined_search instead)
    - User asks any analytical question (use combined_search instead)

    This returns ONLY variable metadata (names, descriptions, codelists).
    For statistics or analysis, use combined_search instead.

    Args:
        input: Search parameters
        ctx: MCP context

    Returns:
        Matching variables and codelists from the data dictionary (metadata only)
    """
    await ctx.info(f"Searching data dictionary for: {input.query}")

    try:
        data_dict = get_data_dictionary()
        codelists = get_codelists() if input.include_codelists else {}

        query_lower = input.query.lower()

        # Search variables
        variable_matches = []
        for table_name, records in data_dict.items():
            for record in records:
                searchable = " ".join(
                    [
                        str(record.get("Question Short Name (Databank Fieldname)", "")),
                        str(record.get("Question", "")),
                        str(record.get("Module", "")),
                        str(record.get("Code List or format", "")),
                        str(record.get("Notes", "")),
                    ]
                ).lower()

                if query_lower in searchable:
                    variable_matches.append(
                        {
                            "table": record.get("__table__", table_name),
                            "field_name": record.get(
                                "Question Short Name (Databank Fieldname)"
                            ),
                            "description": record.get("Question"),
                            "type": record.get("Type"),
                            "codelist_ref": record.get("Code List or format"),
                            "module": record.get("Module"),
                            "form": record.get("Form"),
                            "notes": record.get("Notes"),
                        }
                    )

        # Search codelists
        codelist_matches = []
        if input.include_codelists:
            for name, values in codelists.items():
                if query_lower in name.lower():
                    codelist_matches.append(
                        {
                            "codelist_name": name,
                            "values": [
                                {
                                    "code": v.get("Codes"),
                                    "description": v.get("Descriptors"),
                                }
                                for v in values
                            ],
                        }
                    )
                else:
                    # Search in descriptors
                    for v in values:
                        if query_lower in str(v.get("Descriptors", "")).lower():
                            codelist_matches.append(
                                {
                                    "codelist_name": name,
                                    "values": [
                                        {
                                            "code": val.get("Codes"),
                                            "description": val.get("Descriptors"),
                                        }
                                        for val in values
                                    ],
                                }
                            )
                            break

        # Deduplicate codelist matches
        seen = set()
        unique_codelists = []
        for cl in codelist_matches:
            if cl["codelist_name"] not in seen:
                seen.add(cl["codelist_name"])
                unique_codelists.append(cl)

        return {
            "query": input.query,
            "variables_found": len(variable_matches),
            "variables": variable_matches[:50],  # Limit results
            "codelists_found": len(unique_codelists),
            "codelists": unique_codelists[:10],
            "hint": "Use exact field_name values when querying datasets. "
            "For statistics, use combined_search instead.",
        }

    except Exception as e:
        logger.error(f"Dictionary search failed: {e}")
        return {"error": str(e), "query": input.query}
