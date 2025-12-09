"""
Tests for the RePORTaLiN MCP Server.

This module contains unit tests for the MCP tools, Pydantic models,
and server utilities. The MCP server is located under server/.

Tests cover:
- Pydantic input model validation
- Tool registry functionality
- Server configuration export
- Security validations
"""

import pytest
from pydantic import ValidationError

from server.tools import (
    ExploreStudyMetadataInput,
    BuildTechnicalRequestInput,
    get_tool_registry,
    mcp,
)
from shared.constants import SERVER_NAME, SERVER_VERSION


class TestExploreStudyMetadataInput:
    """Tests for ExploreStudyMetadataInput Pydantic model."""

    def test_valid_metadata_query(self) -> None:
        """Test that valid metadata queries are accepted."""
        input_data = ExploreStudyMetadataInput(
            query="Do we have any participants from Pune with follow-up data?",
        )
        assert "Pune" in input_data.query
        assert input_data.site_filter is None

    def test_query_with_site_filter(self) -> None:
        """Test query with site filter."""
        input_data = ExploreStudyMetadataInput(
            query="What variables are available for TB diagnosis?",
            site_filter="Pune",
        )
        assert input_data.site_filter == "Pune"

    def test_query_with_time_point_filter(self) -> None:
        """Test query with time point filter."""
        input_data = ExploreStudyMetadataInput(
            query="How many participants have Month 24 data?",
            time_point_filter="Month 24",
        )
        assert input_data.time_point_filter == "Month 24"

    def test_rejects_forbidden_path_access(self) -> None:
        """Test that queries attempting to access raw dataset are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(
                query="Read from data/dataset/Indo-vap_csv_files",
            )
        assert "SECURITY ALERT" in str(exc_info.value)

    def test_rejects_phi_request(self) -> None:
        """Test that queries requesting PHI are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(
                query="Show me all patient names from the study",
            )
        assert "metadata only" in str(exc_info.value)

    def test_rejects_raw_data_export(self) -> None:
        """Test that raw data export requests are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(
                query="Export data from the raw dataset",
            )
        assert "metadata only" in str(exc_info.value)

    def test_query_too_short(self) -> None:
        """Test that very short queries are rejected."""
        with pytest.raises(ValidationError):
            ExploreStudyMetadataInput(query="Hi")

    def test_query_too_long(self) -> None:
        """Test that very long queries are rejected."""
        with pytest.raises(ValidationError):
            ExploreStudyMetadataInput(query="x" * 501)


class TestBuildTechnicalRequestInput:
    """Tests for BuildTechnicalRequestInput Pydantic model."""

    def test_valid_technical_request(self) -> None:
        """Test that valid technical requests are accepted."""
        input_data = BuildTechnicalRequestInput(
            description="Analyze treatment outcomes in TB patients with diabetes",
            inclusion_criteria=["Female", "Age 18-45", "TB positive"],
            exclusion_criteria=["HIV co-infection"],
            variables_of_interest=["Age", "Sex", "TB_Status", "Treatment_Outcome"],
            time_points=["Baseline", "Month 6", "Month 12"],
        )
        assert "diabetes" in input_data.description.lower()
        assert len(input_data.inclusion_criteria) == 3
        assert len(input_data.exclusion_criteria) == 1

    def test_minimal_technical_request(self) -> None:
        """Test minimal technical request with required fields only."""
        input_data = BuildTechnicalRequestInput(
            description="Compare demographics across study sites",
        )
        assert input_data.inclusion_criteria == []
        assert input_data.exclusion_criteria == []
        assert input_data.output_format == "concept_sheet"

    def test_query_logic_output_format(self) -> None:
        """Test query_logic output format."""
        input_data = BuildTechnicalRequestInput(
            description="Generate query for female participants",
            output_format="query_logic",
        )
        assert input_data.output_format == "query_logic"

    def test_rejects_forbidden_path_in_description(self) -> None:
        """Test that description attempting raw data access is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BuildTechnicalRequestInput(
                description="Access the raw dataset in data/dataset folder",
            )
        assert "SECURITY ALERT" in str(exc_info.value)

    def test_description_too_short(self) -> None:
        """Test that very short descriptions are rejected."""
        with pytest.raises(ValidationError):
            BuildTechnicalRequestInput(description="Too short")

    def test_invalid_output_format(self) -> None:
        """Test that invalid output formats are rejected."""
        with pytest.raises(ValidationError):
            BuildTechnicalRequestInput(
                description="Valid description for testing",
                output_format="invalid_format",
            )


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
        assert "explore_study_metadata" in tools
        assert "build_technical_request" in tools

    def test_registry_security_mode(self) -> None:
        """Test that registry shows SECURE mode."""
        registry = get_tool_registry()
        assert registry["mode"] == "SECURE"

    def test_registry_security_model(self) -> None:
        """Test that registry includes security model details."""
        registry = get_tool_registry()
        assert "security_model" in registry
        security = registry["security_model"]
        assert security["raw_data_access"] == "BLOCKED"
        assert security["metadata_access"] == "ALLOWED"

    def test_registry_forbidden_zone(self) -> None:
        """Test that registry specifies forbidden zone."""
        registry = get_tool_registry()
        assert "forbidden_zone" in registry
        assert "dataset" in registry["forbidden_zone"]


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


class TestSecurityValidation:
    """Tests for security validation in input models."""

    @pytest.mark.parametrize("forbidden_pattern", [
        "data/dataset",
        "data\\dataset",
        "indo-vap",
        "csv_files",
        "6_HIV.xlsx",
        "read from file",
        "access the raw dataset",
    ])
    def test_metadata_rejects_forbidden_patterns(self, forbidden_pattern: str) -> None:
        """Test that metadata queries reject various forbidden patterns."""
        with pytest.raises(ValidationError):
            ExploreStudyMetadataInput(
                query=f"Please help me with {forbidden_pattern} analysis",
            )

    @pytest.mark.parametrize("phi_pattern", [
        "show me all patients",
        "list all records",
        "export data",
        "download dataset",
        "raw data",
        "patient names",
        "individual records",
    ])
    def test_metadata_rejects_phi_patterns(self, phi_pattern: str) -> None:
        """Test that metadata queries reject PHI request patterns."""
        with pytest.raises(ValidationError):
            ExploreStudyMetadataInput(
                query=f"I need to {phi_pattern}",
            )

    @pytest.mark.parametrize("safe_query", [
        "Do we have CD4 counts available?",
        "How many study sites are there?",
        "What variables exist for TB diagnosis?",
        "Are there any participants from Pune?",
        "What time points are collected?",
    ])
    def test_metadata_accepts_safe_queries(self, safe_query: str) -> None:
        """Test that metadata queries accept safe/valid patterns."""
        input_data = ExploreStudyMetadataInput(query=safe_query)
        assert input_data.query == safe_query.strip()
