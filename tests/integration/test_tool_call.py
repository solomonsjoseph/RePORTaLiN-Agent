"""
Test actual tool calls to verify the MCP server works end-to-end.

This is an integration test that verifies complete MCP tool functionality.
Run with: pytest tests/integration/ -m integration

Tests cover all 4 implemented MCP tools:
- query_database: SQL-like queries with validation
- search_dictionary: Data dictionary search
- fetch_metrics: Aggregate statistics with k-anonymity
- health_check: Server status verification
"""

import pytest

from server.tools import (
    FetchMetricsInput,
    MetricType,
    QueryDatabaseInput,
    SearchDictionaryInput,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.mcp,
    pytest.mark.asyncio,
]


# =============================================================================
# query_database Tool Tests
# =============================================================================

async def test_query_database_valid_select():
    """Test query_database with a valid SELECT query."""
    from server.tools import query_database

    input_data = QueryDatabaseInput(
        query="SELECT * FROM patients WHERE age > 18",
        limit=10,
        include_metadata=False,
    )

    result = await query_database(input_data)

    assert result["success"] is True
    assert "data" in result
    assert isinstance(result["data"], list)
    assert result["row_count"] <= 10
    assert "execution_time_ms" in result


async def test_query_database_with_metadata():
    """Test query_database with metadata included."""
    from server.tools import query_database

    input_data = QueryDatabaseInput(
        query="SELECT id, name FROM patients LIMIT 5",
        limit=5,
        include_metadata=True,
    )

    result = await query_database(input_data)

    assert result["success"] is True
    assert "metadata" in result
    assert "columns" in result["metadata"]


async def test_query_database_rejects_insert():
    """Test that query_database rejects INSERT statements."""
    with pytest.raises(ValueError, match="SELECT"):
        QueryDatabaseInput(
            query="INSERT INTO patients VALUES (1, 'test')",
            limit=10,
        )


async def test_query_database_rejects_drop():
    """Test that query_database rejects DROP statements."""
    with pytest.raises(ValueError, match="SELECT"):
        QueryDatabaseInput(
            query="DROP TABLE patients",
            limit=10,
        )


# =============================================================================
# search_dictionary Tool Tests
# =============================================================================

async def test_search_dictionary_basic():
    """Test search_dictionary with basic search term."""
    from server.tools import search_dictionary

    input_data = SearchDictionaryInput(
        search_term="patient",
        include_values=True,
    )

    result = await search_dictionary(input_data)

    assert result["success"] is True
    assert "matches" in result
    assert len(result["matches"]) >= 1
    assert result["search_term"] == "patient"


async def test_search_dictionary_with_table_filter():
    """Test search_dictionary with table filter."""
    from server.tools import search_dictionary

    input_data = SearchDictionaryInput(
        search_term="diagnosis",
        table_filter="clinical_data",
        include_values=False,
    )

    result = await search_dictionary(input_data)

    assert result["success"] is True
    assert result["matches"][0]["table"] == "clinical_data"


async def test_search_dictionary_sanitizes_input():
    """Test that search_dictionary sanitizes potentially dangerous input."""
    input_data = SearchDictionaryInput(
        search_term="patient; DROP TABLE--",
    )

    # Validator should strip dangerous characters
    assert ";" not in input_data.search_term
    assert "--" not in input_data.search_term


# =============================================================================
# fetch_metrics Tool Tests
# =============================================================================

async def test_fetch_metrics_count():
    """Test fetch_metrics with COUNT metric type."""
    from server.tools import fetch_metrics

    input_data = FetchMetricsInput(
        metric_type=MetricType.COUNT,
        field_name="patients",
    )

    result = await fetch_metrics(input_data)

    assert result["success"] is True
    assert result["metric_type"] == "count"
    assert result["field_name"] == "patients"
    assert isinstance(result["result"], (int, float))


async def test_fetch_metrics_average():
    """Test fetch_metrics with AVERAGE metric type."""
    from server.tools import fetch_metrics

    input_data = FetchMetricsInput(
        metric_type=MetricType.AVERAGE,
        field_name="age",
    )

    result = await fetch_metrics(input_data)

    assert result["success"] is True
    assert result["metric_type"] == "average"
    assert isinstance(result["result"], (int, float))


async def test_fetch_metrics_with_groupby():
    """Test fetch_metrics with group_by field."""
    from server.tools import fetch_metrics

    input_data = FetchMetricsInput(
        metric_type=MetricType.DISTRIBUTION,
        field_name="age",
        group_by="age_range",
    )

    result = await fetch_metrics(input_data)

    assert result["success"] is True
    assert result["group_by"] == "age_range"


async def test_fetch_metrics_with_filters():
    """Test fetch_metrics with filter conditions."""
    from server.tools import fetch_metrics

    input_data = FetchMetricsInput(
        metric_type=MetricType.SUM,
        field_name="visit_count",
        filters={"status": "active", "age_min": 18},
    )

    result = await fetch_metrics(input_data)

    assert result["success"] is True
    assert result["filters_applied"] is True


# =============================================================================
# health_check Tool Tests
# =============================================================================

async def test_health_check():
    """Test health_check returns proper status."""
    from server.tools import health_check

    result = await health_check()

    assert result["status"] == "healthy"
    assert "version" in result
    assert "protocol_version" in result
    assert "capabilities" in result
    assert result["capabilities"]["tools"] is True


async def test_health_check_includes_privacy_settings():
    """Test health_check includes privacy configuration."""
    from server.tools import health_check

    result = await health_check()

    assert "privacy" in result
    assert "k_anonymity_threshold" in result["privacy"]
    assert result["privacy"]["k_anonymity_threshold"] >= 1
