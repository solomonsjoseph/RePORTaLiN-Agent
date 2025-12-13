"""MCP Tools package for RePORTaLiN.

This package provides the refactored MCP tool architecture with:
- 4 core tools (prompt_enhancer, combined_search, search_data_dictionary, search_cleaned_dataset)
- Shared utilities (_models, _loaders, _analyzers)
- FastMCP server setup and registration (registry)

All tools are registered with the FastMCP server instance and ready to use.
"""

from __future__ import annotations

# Re-export the FastMCP server instance and registry
from reportalin.server.tools.registry import get_tool_registry, mcp

# Re-export the 4 tools
from reportalin.server.tools.combined_search import combined_search
from reportalin.server.tools.prompt_enhancer import prompt_enhancer
from reportalin.server.tools.search_cleaned_dataset import search_cleaned_dataset
from reportalin.server.tools.search_data_dictionary import search_data_dictionary

# Re-export input models for use in tests
from reportalin.server.tools._models import (
    CombinedSearchInput,
    PromptEnhancerInput,
    SearchCleanedDatasetInput,
    SearchDataDictionaryInput,
)

__all__ = [
    # FastMCP server instance (main export)
    "mcp",
    # Registry function
    "get_tool_registry",
    # 4 core tools
    "prompt_enhancer",
    "combined_search",
    "search_data_dictionary",
    "search_cleaned_dataset",
    # Input models
    "CombinedSearchInput",
    "PromptEnhancerInput",
    "SearchCleanedDatasetInput",
    "SearchDataDictionaryInput",
]
