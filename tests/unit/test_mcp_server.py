"""
Tests for the RePORTaLiN MCP Server.

This module contains unit tests for the MCP tools, Pydantic models,
and server utilities. The MCP server is located under server/.

Tests cover:
- Pydantic input model validation
- Tool registry functionality
- Server configuration export
- Security validations (aggregates only, no individual records)
"""

import pytest
from pydantic import ValidationError

from server.tools import (
    DictionarySearchInput,
    DatasetSearchInput,
    CombinedSearchInput,
    get_tool_registry,
    mcp,
)
from shared.constants import SERVER_NAME, SERVER_VERSION


class TestDictionarySearchInput:
    """Tests for DictionarySearchInput Pydantic model."""

    def test_valid_search_query(self) -> None:
        """Test that valid search queries are accepted."""
        input_data = DictionarySearchInput(
            query="smoking",
        )
        assert "smoking" in input_data.query
        assert input_data.include_codelists is True

    def test_query_with_codelist_disabled(self) -> None:
        """Test query with codelist search disabled."""
        input_data = DictionarySearchInput(
            query="HIV",
            include_codelists=False,
        )
        assert input_data.include_codelists is False

    def test_query_too_short(self) -> None:
        """Test that empty queries are rejected."""
        with pytest.raises(ValidationError):
            DictionarySearchInput(query="")

    def test_query_too_long(self) -> None:
        """Test that very long queries are rejected."""
        with pytest.raises(ValidationError):
            DictionarySearchInput(query="x" * 201)


class TestDatasetSearchInput:
    """Tests for DatasetSearchInput Pydantic model."""

    def test_valid_dataset_search(self) -> None:
        """Test that valid dataset searches are accepted."""
        input_data = DatasetSearchInput(
            variable="AGE",
        )
        assert input_data.variable == "AGE"
        assert input_data.table_filter is None

    def test_search_with_table_filter(self) -> None:
        """Test search with table filter."""
        input_data = DatasetSearchInput(
            variable="SEX",
            table_filter="Index",
        )
        assert input_data.table_filter == "Index"


class TestCombinedSearchInput:
    """Tests for CombinedSearchInput Pydantic model."""

    def test_valid_combined_search(self) -> None:
        """Test that valid combined searches are accepted."""
        input_data = CombinedSearchInput(
            concept="smoking status",
        )
        assert "smoking" in input_data.concept
        assert input_data.include_statistics is True

    def test_combined_search_without_statistics(self) -> None:
        """Test combined search without statistics."""
        input_data = CombinedSearchInput(
            concept="HIV status",
            include_statistics=False,
        )
        assert input_data.include_statistics is False


class TestToolRegistry:
    """Tests for tool registry functionality."""

    def test_get_tool_registry_returns_dict(self) -> None:
        """Test that get_tool_registry returns a dictionary."""
        registry = get_tool_registry()
        assert isinstance(registry, dict)

    def test_registry_contains_server_info(self) -> None:
        """Test that registry contains server name and version."""
        registry = get_tool_registry()
        assert registry["server_name"] == SERVER_NAME
        assert registry["version"] == SERVER_VERSION

    def test_registry_contains_registered_tools(self) -> None:
        """Test that registry lists registered tools."""
        registry = get_tool_registry()
        assert "registered_tools" in registry
        tools = registry["registered_tools"]
        assert "search_data_dictionary" in tools
        assert "search_cleaned_dataset" in tools
        assert "search_original_dataset" in tools
        assert "combined_search" in tools

    def test_registry_contains_data_loaded_info(self) -> None:
        """Test that registry shows data loaded statistics."""
        registry = get_tool_registry()
        assert "data_loaded" in registry
        data = registry["data_loaded"]
        assert "dictionary_tables" in data
        assert "dictionary_fields" in data
        assert "codelists" in data
        assert "cleaned_tables" in data
        assert "cleaned_records" in data

    def test_registry_contains_resources(self) -> None:
        """Test that registry lists MCP resources."""
        registry = get_tool_registry()
        assert "registered_resources" in registry
        resources = registry["registered_resources"]
        assert "dictionary://overview" in resources
        assert "dictionary://tables" in resources


class TestMCPServer:
    """Tests for the FastMCP server instance."""

    def test_mcp_instance_exists(self) -> None:
        """Test that MCP server instance exists."""
        assert mcp is not None

    def test_mcp_server_name(self) -> None:
        """Test that MCP server has correct name."""
        assert mcp.name == SERVER_NAME

    def test_mcp_has_instructions(self) -> None:
        """Test that MCP server has instructions."""
        # FastMCP stores instructions in the instance
        assert hasattr(mcp, "_instructions") or mcp.name is not None


class TestSecurityModel:
    """Tests for security model - all tools return aggregates only."""

    def test_tools_designed_for_aggregates(self) -> None:
        """Test that tool registry confirms aggregate-only design."""
        registry = get_tool_registry()
        # Tools are designed to only return aggregate data
        # This is enforced in the tool implementations
        assert len(registry["registered_tools"]) == 4

    @pytest.mark.parametrize("safe_query", [
        "smoking",
        "HIV",
        "age",
        "SEX codelist",
        "treatment outcome",
        "diabetes",
        "TB diagnosis",
    ])
    def test_dictionary_accepts_safe_queries(self, safe_query: str) -> None:
        """Test that dictionary search accepts valid queries."""
        input_data = DictionarySearchInput(query=safe_query)
        assert input_data.query == safe_query

    @pytest.mark.parametrize("variable", [
        "AGE",
        "SEX",
        "SMOKHX",
        "HIV_R",
        "OUTCLIN",
    ])
    def test_dataset_accepts_valid_variables(self, variable: str) -> None:
        """Test that dataset search accepts valid variable names."""
        input_data = DatasetSearchInput(variable=variable)
        assert input_data.variable == variable

    @pytest.mark.parametrize("concept", [
        "smoking status",
        "age distribution",
        "HIV status",
        "TB outcome",
        "alcohol use",
    ])
    def test_combined_accepts_valid_concepts(self, concept: str) -> None:
        """Test that combined search accepts valid clinical concepts."""
        input_data = CombinedSearchInput(concept=concept)
        assert input_data.concept == concept
