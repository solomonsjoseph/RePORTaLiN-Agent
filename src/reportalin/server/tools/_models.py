"""Pydantic input models for MCP tools.

This module defines the input validation schemas for all 4 MCP tools.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field

__all__ = [
    "PromptEnhancerInput",
    "CombinedSearchInput",
    "SearchDataDictionaryInput",
    "SearchCleanedDatasetInput",
]


class PromptEnhancerInput(BaseModel):
    """Input for the prompt enhancer tool (primary entry point).

    This tool analyzes user queries, enhances them for accuracy, ensures privacy
    compliance, and routes to appropriate specialized tools.
    """

    user_query: Annotated[
        str,
        Field(
            description="Natural language question from the user. Can be vague or imprecise. "
            "Examples: 'How many TB patients?', 'What variables track HIV?', "
            "'Show me diabetes statistics', 'Compare outcomes by site'",
            min_length=5,
            max_length=500,
        ),
    ]

    context: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description="Optional context from previous queries for multi-turn conversations",
        ),
    ]

    user_confirmation: Annotated[
        bool,
        Field(
            default=False,
            description="Set to True after user confirms the interpretation is correct",
        ),
    ]


class CombinedSearchInput(BaseModel):
    """Input for combined dictionary + dataset search (DEFAULT tool)."""

    concept: Annotated[
        str,
        Field(
            description="Clinical concept to analyze. "
            "Examples: 'smoking status', 'age distribution', 'HIV status', 'TB outcome'",
        ),
    ]

    include_statistics: Annotated[
        bool,
        Field(default=True, description="Include dataset statistics if variable found"),
    ]


class SearchDataDictionaryInput(BaseModel):
    """Input for searching the data dictionary (metadata only)."""

    query: Annotated[
        str,
        Field(
            description="Search term for variable names, descriptions, or codelists. "
            "Examples: 'HIV', 'age', 'smoking', 'SEX codelist', 'outcome'",
            min_length=1,
            max_length=200,
        ),
    ]

    include_codelists: Annotated[
        bool,
        Field(default=True, description="Include codelist searches"),
    ]


class SearchCleanedDatasetInput(BaseModel):
    """Input for searching the cleaned de-identified dataset."""

    variable: Annotated[
        str,
        Field(
            description="Variable name to analyze. Use search_data_dictionary first to find exact names. "
            "Examples: 'AGE', 'SEX', 'SMOKHX', 'HIV_R'",
        ),
    ]

    table_filter: Annotated[
        str | None,
        Field(default=None, description="Optional: limit to specific table"),
    ]
