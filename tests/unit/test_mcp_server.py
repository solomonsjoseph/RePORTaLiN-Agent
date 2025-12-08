"""
Tests for the RePORTaLiN MCP Server.

This module contains unit tests for the MCP tools, Pydantic models,
and server utilities. The MCP server is located under server/.

Tests cover:
- Pydantic input model validation
- Tool registry functionality
- Server configuration export
- Resource definitions
"""

import pytest
from pydantic import ValidationError

from server.tools import (
    QueryDatabaseInput,
    SearchDictionaryInput,
    FetchMetricsInput,
    MetricType,
    get_tool_registry,
    mcp,
)
from shared.constants import SERVER_NAME, SERVER_VERSION


class TestQueryDatabaseInput:
    """Tests for QueryDatabaseInput Pydantic model."""

    def test_valid_select_query(self) -> None:
        """Test that valid SELECT queries are accepted."""
        input_data = QueryDatabaseInput(
            query="SELECT * FROM patients WHERE age > 18",
            limit=100,
        )
        assert input_data.query.startswith("SELECT")
        assert input_data.limit == 100

    def test_query_whitespace_trimmed(self) -> None:
        """Test that query whitespace is trimmed."""
        input_data = QueryDatabaseInput(
            query="  SELECT * FROM patients  ",
            limit=10,
        )
        assert input_data.query == "SELECT * FROM patients"

    def test_rejects_insert_query(self) -> None:
        """Test that INSERT queries are rejected."""
        with pytest.raises(ValidationError):
            QueryDatabaseInput(
                query="INSERT INTO patients VALUES (1, 'test')",
            )

    def test_rejects_update_query(self) -> None:
        """Test that UPDATE queries are rejected."""
        with pytest.raises(ValidationError):
            QueryDatabaseInput(
                query="UPDATE patients SET name = 'test' WHERE id = 1",
            )

    def test_rejects_delete_query(self) -> None:
        """Test that DELETE queries are rejected."""
        with pytest.raises(ValidationError):
            QueryDatabaseInput(
                query="DELETE FROM patients WHERE id = 1",
            )

    def test_rejects_drop_query(self) -> None:
        """Test that DROP queries are rejected."""
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query="DROP TABLE patients")

    def test_rejects_query_too_short(self) -> None:
        """Test that queries shorter than min_length are rejected."""
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query="SELECT")

    def test_limit_bounds(self) -> None:
        """Test limit parameter bounds validation."""
        # Valid limit
        valid = QueryDatabaseInput(
            query="SELECT * FROM patients",
            limit=500,
        )
        assert valid.limit == 500

        # Limit too low
        with pytest.raises(ValidationError):
            QueryDatabaseInput(
                query="SELECT * FROM patients",
                limit=0,
            )

        # Limit too high
        with pytest.raises(ValidationError):
            QueryDatabaseInput(
                query="SELECT * FROM patients",
                limit=2000,
            )


class TestSearchDictionaryInput:
    """Tests for SearchDictionaryInput Pydantic model."""

    def test_valid_search_term(self) -> None:
        """Test that valid search terms are accepted."""
        input_data = SearchDictionaryInput(
            search_term="patient_id",
            include_values=True,
        )
        assert input_data.search_term == "patient_id"
        assert input_data.include_values is True

    def test_sanitizes_dangerous_characters(self) -> None:
        """Test that dangerous characters are removed from search term."""
        input_data = SearchDictionaryInput(
            search_term="patient; DROP TABLE--",
        )
        assert ";" not in input_data.search_term
        assert "--" not in input_data.search_term

    def test_search_term_min_length(self) -> None:
        """Test that search term must meet minimum length."""
        with pytest.raises(ValidationError):
            SearchDictionaryInput(search_term="a")

    def test_optional_table_filter(self) -> None:
        """Test optional table_filter parameter."""
        input_data = SearchDictionaryInput(
            search_term="diagnosis",
            table_filter="clinical_data",
        )
        assert input_data.table_filter == "clinical_data"


class TestFetchMetricsInput:
    """Tests for FetchMetricsInput Pydantic model."""

    def test_valid_count_metric(self) -> None:
        """Test valid COUNT metric input."""
        input_data = FetchMetricsInput(
            metric_type=MetricType.COUNT,
            field_name="patients",
        )
        assert input_data.metric_type == MetricType.COUNT
        assert input_data.field_name == "patients"

    def test_all_metric_types(self) -> None:
        """Test all metric types are valid."""
        for metric_type in MetricType:
            input_data = FetchMetricsInput(
                metric_type=metric_type,
                field_name="test_field",
            )
            assert input_data.metric_type == metric_type

    def test_optional_group_by(self) -> None:
        """Test optional group_by parameter."""
        input_data = FetchMetricsInput(
            metric_type=MetricType.AVERAGE,
            field_name="age",
            group_by="gender",
        )
        assert input_data.group_by == "gender"

    def test_optional_filters(self) -> None:
        """Test optional filters parameter."""
        input_data = FetchMetricsInput(
            metric_type=MetricType.SUM,
            field_name="visit_count",
            filters={"status": "active"},
        )
        assert input_data.filters == {"status": "active"}


class TestToolRegistry:
    """Tests for the tool registry utility."""

    def test_registry_has_server_info(self) -> None:
        """Test registry includes server name and version."""
        registry = get_tool_registry()
        assert registry["server_name"] == SERVER_NAME
        assert registry["version"] == SERVER_VERSION

    def test_registry_lists_all_tools(self) -> None:
        """Test registry lists all registered tools."""
        registry = get_tool_registry()
        tools = registry["registered_tools"]
        
        assert "query_database" in tools
        assert "search_dictionary" in tools
        assert "fetch_metrics" in tools
        assert "health_check" in tools

    def test_registry_lists_resources(self) -> None:
        """Test registry lists registered resources."""
        registry = get_tool_registry()
        resources = registry["registered_resources"]
        
        assert "config://server" in resources


class TestMCPServerInstance:
    """Tests for the FastMCP server instance."""

    @pytest.mark.asyncio
    async def test_mcp_lists_tools(self) -> None:
        """Test that mcp.list_tools() returns registered tools."""
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        
        assert len(tool_names) >= 4
        assert "query_database" in tool_names
        assert "health_check" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_tool_schemas_valid(self) -> None:
        """Test that all tool schemas are valid JSON schemas."""
        tools = await mcp.list_tools()
        
        for tool in tools:
            assert tool.name is not None
            assert tool.description is not None
            
            if tool.inputSchema:
                assert tool.inputSchema.get("type") == "object"

    @pytest.mark.asyncio
    async def test_mcp_resources_listed(self) -> None:
        """Test that resources are properly listed."""
        resources = await mcp.list_resources()
        resource_uris = [str(r.uri) for r in resources]
        
        assert "config://server" in resource_uris
