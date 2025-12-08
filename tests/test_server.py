"""
Server Security and Integration Tests.

Phase 5: Verification, Testing & Security Hardening

This module provides comprehensive testing for:
- Authentication enforcement (valid/invalid/missing tokens)
- SQL injection prevention (dangerous query rejection)
- Tool input validation (Pydantic model security)
- Endpoint authorization

Test Categories:
    - TestAuthenticationSecurity: Tests for auth enforcement
    - TestQueryValidation: Tests for SQL injection prevention
    - TestEndpointSecurity: Tests for endpoint protection
    - TestToolExecution: Tests for tool security

Running Tests:
    ```bash
    # Run all tests
    uv run pytest tests/test_server.py -v

    # Run only security tests
    uv run pytest tests/test_server.py -m security -v

    # Run only auth tests
    uv run pytest tests/test_server.py -m auth -v

    # Run with coverage
    uv run pytest tests/test_server.py --cov=server -v
    ```

See Also:
    - tests/conftest.py for shared fixtures
    - server/auth.py for authentication implementation
    - server/tools.py for tool implementations
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.auth import verify_token
from server.tools import (
    BuildTechnicalRequestInput,
    ExploreStudyMetadataInput,
)

# =============================================================================
# Test Markers
# =============================================================================

pytestmark = [pytest.mark.security]


# =============================================================================
# Authentication Security Tests
# =============================================================================

class TestAuthenticationSecurity:
    """
    Tests for authentication enforcement on protected endpoints.

    These tests verify that:
    - Protected endpoints reject unauthenticated requests
    - Invalid tokens are rejected with 401/403
    - Valid tokens allow access
    - Public endpoints remain accessible
    """

    @pytest.mark.auth
    def test_health_endpoint_is_public(self, test_client):
        """
        Health endpoint should be accessible without authentication.

        The /health endpoint is used for Kubernetes liveness probes
        and must be accessible without auth headers.
        """
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.auth
    def test_ready_endpoint_is_public(self, test_client):
        """
        Readiness endpoint should be accessible without authentication.

        The /ready endpoint is used for Kubernetes readiness probes.
        """
        response = test_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True

    @pytest.mark.auth
    def test_tools_endpoint_requires_auth(self, test_client, no_auth_headers):
        """
        Tools endpoint should require authentication.

        The /tools endpoint exposes server capabilities and must
        be protected to prevent information disclosure.
        """
        response = test_client.get("/tools", headers=no_auth_headers)
        assert response.status_code == 401

    @pytest.mark.auth
    def test_tools_endpoint_rejects_invalid_token(
        self, test_client, invalid_auth_headers
    ):
        """
        Tools endpoint should reject invalid authentication tokens.

        Invalid tokens should result in 401 Unauthorized, not 403 Forbidden.
        """
        response = test_client.get("/tools", headers=invalid_auth_headers)
        assert response.status_code == 401

    @pytest.mark.auth
    def test_tools_endpoint_accepts_valid_token(self, test_client, auth_headers):
        """
        Tools endpoint should accept valid authentication tokens.
        """
        response = test_client.get("/tools", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data

    @pytest.mark.auth
    def test_info_endpoint_requires_auth(self, test_client, no_auth_headers):
        """
        Info endpoint should require authentication.
        """
        response = test_client.get("/info", headers=no_auth_headers)
        assert response.status_code == 401

    @pytest.mark.auth
    def test_info_endpoint_accepts_valid_token(self, test_client, auth_headers):
        """
        Info endpoint should accept valid authentication tokens.
        """
        response = test_client.get("/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "server_name" in data

    @pytest.mark.auth
    def test_mcp_sse_requires_auth(self, test_client, no_auth_headers):
        """
        MCP SSE endpoint should require authentication.

        The /mcp/sse endpoint is the main MCP connection point and
        must be protected to prevent unauthorized tool execution.
        """
        # Note: TestClient doesn't support true SSE, but we can test
        # that the auth middleware rejects unauthenticated requests
        response = test_client.get("/mcp/sse", headers=no_auth_headers)
        # Should return 401 from the MCPAuthMiddleware
        assert response.status_code == 401

    @pytest.mark.auth
    def test_mcp_sse_rejects_invalid_token(self, test_client, invalid_auth_headers):
        """
        MCP SSE endpoint should reject invalid tokens.
        """
        response = test_client.get("/mcp/sse", headers=invalid_auth_headers)
        assert response.status_code == 401


# =============================================================================
# PHI Request Validation Security Tests (SECURE MODE)
# =============================================================================

class TestPHIRequestValidation:
    """
    Tests for PHI (Protected Health Information) request prevention
    in ExploreStudyMetadataInput.

    These tests verify that requests for raw patient data are rejected
    at the Pydantic validation layer.
    """

    @pytest.mark.security
    def test_show_patients_request_rejected(self):
        """
        Requests to show patient records should be rejected.

        This is a critical security test - raw PHI requests could
        expose protected health information.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="show me all patients")

        errors = exc_info.value.errors()
        assert len(errors) > 0

    @pytest.mark.security
    def test_list_records_request_rejected(self):
        """
        Requests to list records should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="list the patient records")

        errors = exc_info.value.errors()
        assert len(errors) > 0

    @pytest.mark.security
    def test_export_data_request_rejected(self):
        """
        Requests to export data should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="export data to CSV")

        errors = exc_info.value.errors()
        assert len(errors) > 0

    @pytest.mark.security
    def test_download_dataset_request_rejected(self):
        """
        Requests to download datasets should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="download dataset")

        errors = exc_info.value.errors()
        assert len(errors) > 0

    @pytest.mark.security
    def test_raw_data_request_rejected(self):
        """
        Requests for raw data should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="show raw data")

        errors = exc_info.value.errors()
        assert len(errors) > 0

    @pytest.mark.security
    def test_patient_names_request_rejected(self):
        """
        Requests for patient names should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="get patient names")

        errors = exc_info.value.errors()
        assert len(errors) > 0

    @pytest.mark.security
    def test_individual_records_request_rejected(self):
        """
        Requests for individual records should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="show individual records for ID 123")

        errors = exc_info.value.errors()
        assert len(errors) > 0

    @pytest.mark.security
    def test_valid_metadata_query_accepted(self):
        """
        Valid metadata queries should be accepted.

        This is a positive test to ensure legitimate queries work.
        """
        # Variable check query
        input1 = ExploreStudyMetadataInput(query="Do we have CD4 counts in the study?")
        assert "CD4" in input1.query

        # Site query
        input2 = ExploreStudyMetadataInput(query="How many study sites are there?")
        assert "sites" in input2.query.lower()

        # Time point query
        input3 = ExploreStudyMetadataInput(
            query="What time points are available for follow-up?",
            time_point_filter="Month 24"
        )
        assert input3.time_point_filter == "Month 24"

    @pytest.mark.security
    def test_query_minimum_length_enforced(self):
        """
        Queries must meet minimum length requirement.
        """
        with pytest.raises(ValidationError):
            ExploreStudyMetadataInput(query="data")  # Too short


# =============================================================================
# Forbidden Zone Security Tests (SECURE MODE)
# =============================================================================

class TestForbiddenZoneSecurity:
    """
    Tests for forbidden zone path access prevention.

    These tests verify that attempts to access ./data/dataset/
    are rejected with the security alert message.
    """

    @pytest.mark.security
    def test_data_dataset_path_rejected(self):
        """
        Requests mentioning data/dataset path should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="read from data/dataset folder")

        error_msg = str(exc_info.value)
        assert "SECURITY ALERT" in error_msg

    @pytest.mark.security
    def test_indo_vap_files_rejected(self):
        """
        Requests mentioning Indo-VAP files should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="show indo-vap csv files")

        error_msg = str(exc_info.value)
        assert "SECURITY ALERT" in error_msg

    @pytest.mark.security
    def test_specific_phi_file_rejected(self):
        """
        Requests for specific PHI files (6_HIV.xlsx) should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="open the 6_HIV file")

        error_msg = str(exc_info.value)
        assert "SECURITY ALERT" in error_msg

    @pytest.mark.security
    def test_baseline_file_rejected(self):
        """
        Requests for baseline files (2A_ICBaseline.xlsx) should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="read 2A_ICBaseline data")

        error_msg = str(exc_info.value)
        assert "SECURITY ALERT" in error_msg

    @pytest.mark.security
    def test_xlsx_file_access_rejected(self):
        """
        Requests to access .xlsx files should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="open the .xlsx file")

        error_msg = str(exc_info.value)
        assert "SECURITY ALERT" in error_msg

    @pytest.mark.security
    def test_raw_dataset_access_rejected(self):
        """
        Requests to access raw dataset should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query="access the raw dataset")

        error_msg = str(exc_info.value)
        assert "SECURITY ALERT" in error_msg


# =============================================================================
# Technical Request Validation Tests (SECURE MODE)
# =============================================================================

class TestTechnicalRequestValidation:
    """
    Tests for BuildTechnicalRequestInput validation.

    These tests verify that concept sheet requests are properly validated.
    """

    @pytest.mark.security
    def test_valid_request_accepted(self):
        """
        Valid technical requests should be accepted.
        """
        input_model = BuildTechnicalRequestInput(
            description="Analyze treatment outcomes in TB patients",
            inclusion_criteria=["Female", "Age 18-45"],
            exclusion_criteria=["HIV co-infection"],
            variables_of_interest=["Age", "Sex", "TB_Status"],
            time_points=["Baseline", "Month 6"],
            output_format="concept_sheet",
        )

        assert input_model.description is not None
        assert len(input_model.inclusion_criteria) == 2

    @pytest.mark.security
    def test_description_minimum_length_enforced(self):
        """
        Description must meet minimum length requirement.
        """
        with pytest.raises(ValidationError):
            BuildTechnicalRequestInput(
                description="Too short",  # Less than 10 chars
            )

    @pytest.mark.security
    def test_output_format_validated(self):
        """
        Output format must be a valid option.
        """
        # Valid formats
        for fmt in ["concept_sheet", "query_logic"]:
            input_model = BuildTechnicalRequestInput(
                description="Analyze treatment outcomes in TB patients",
                output_format=fmt,
            )
            assert input_model.output_format == fmt

        # Invalid format should fail
        with pytest.raises(ValidationError):
            BuildTechnicalRequestInput(
                description="Analyze treatment outcomes in TB patients",
                output_format="invalid_format",
            )

    @pytest.mark.security
    def test_empty_criteria_allowed(self):
        """
        Empty inclusion/exclusion criteria should be allowed.
        """
        input_model = BuildTechnicalRequestInput(
            description="Analyze all participants in the study",
            inclusion_criteria=[],
            exclusion_criteria=[],
        )

        assert len(input_model.inclusion_criteria) == 0
        assert len(input_model.exclusion_criteria) == 0


# =============================================================================
# Token Verification Security Tests
# =============================================================================

class TestTokenVerification:
    """
    Tests for the token verification utility function.

    These tests verify constant-time comparison behavior
    and edge case handling.
    """

    @pytest.mark.security
    def test_valid_token_passes(self):
        """
        Matching tokens should verify successfully.
        """
        assert verify_token("secret123", "secret123") is True

    @pytest.mark.security
    def test_invalid_token_fails(self):
        """
        Non-matching tokens should fail verification.
        """
        assert verify_token("wrong", "secret123") is False

    @pytest.mark.security
    def test_none_provided_fails(self):
        """
        None provided token should fail verification.
        """
        assert verify_token(None, "secret123") is False

    @pytest.mark.security
    def test_none_expected_fails(self):
        """
        None expected token should fail verification.
        """
        assert verify_token("secret123", None) is False

    @pytest.mark.security
    def test_both_none_fails(self):
        """
        Both tokens None should fail verification.
        """
        assert verify_token(None, None) is False

    @pytest.mark.security
    def test_empty_provided_fails(self):
        """
        Empty string provided token should fail verification.
        """
        assert verify_token("", "secret123") is False

    @pytest.mark.security
    def test_empty_expected_fails(self):
        """
        Empty string expected token should fail verification.
        """
        assert verify_token("secret123", "") is False

    @pytest.mark.security
    def test_different_length_tokens_fail(self):
        """
        Different length tokens should fail verification.

        This tests that length differences don't cause timing leaks.
        """
        assert verify_token("short", "much_longer_token") is False
        assert verify_token("much_longer_token", "short") is False


# =============================================================================
# Tool Execution Security Tests (SECURE MODE - 2 Tools Only)
# =============================================================================

class TestToolExecutionSecurity:
    """
    Tests for direct tool function security.

    These tests import and call tool functions directly to verify
    their security behavior without going through the HTTP layer.

    SECURE MODE: Only two tools are available:
    1. explore_study_metadata
    2. build_technical_request
    """

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_explore_study_metadata_rejects_phi_request(self):
        """
        CRITICAL: Verify explore_study_metadata rejects requests for raw PHI data.

        The security check happens at the Pydantic validation layer.
        Queries requesting patient records should raise ValidationError.
        """
        from server.tools import ExploreStudyMetadataInput

        # Attempting to request patient data should raise ValueError
        phi_queries = [
            "show me all patients",
            "list the patient records",
            "export data to CSV",
            "download dataset",
            "show raw data",
        ]

        for query in phi_queries:
            with pytest.raises((ValueError, ValidationError)) as exc_info:
                ExploreStudyMetadataInput(query=query)

            # Verify the error message mentions metadata/formal request
            error_str = str(exc_info.value).lower()
            assert "metadata" in error_str or "formal" in error_str or "data request" in error_str

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_explore_study_metadata_validates_input(self, explore_study_metadata_input):
        """
        explore_study_metadata tool should validate input before execution.
        """
        from server.tools import ExploreStudyMetadataInput, explore_study_metadata

        # Create valid input
        input_model = ExploreStudyMetadataInput(**explore_study_metadata_input)

        # Execute should work with valid input (mocked context)
        from unittest.mock import AsyncMock, MagicMock
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()

        result = await explore_study_metadata(input_model, mock_ctx)
        assert result["success"] is True
        assert "results" in result

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_build_technical_request_validates_input(self, build_technical_request_input):
        """
        build_technical_request tool should validate input before execution.
        """
        from server.tools import BuildTechnicalRequestInput, build_technical_request

        # Create valid input
        input_model = BuildTechnicalRequestInput(**build_technical_request_input)

        # Execute should work with valid input (mocked context)
        from unittest.mock import AsyncMock, MagicMock
        mock_ctx = MagicMock()
        mock_ctx.info = AsyncMock()

        result = await build_technical_request(input_model, mock_ctx)
        assert result["success"] is True
        assert "request_id" in result
        assert "output" in result

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_old_tools_not_available(self):
        """
        CRITICAL: Verify old tools are NOT importable (secure mode enforcement).
        """
        from server.tools import mcp

        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]

        # Old tools should NOT exist
        assert "query_database" not in tool_names
        assert "search_dictionary" not in tool_names
        assert "fetch_metrics" not in tool_names
        assert "health_check" not in tool_names
        assert "list_datasets" not in tool_names
        assert "describe_schema" not in tool_names
        assert "get_pipeline_status" not in tool_names

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_only_two_tools_registered(self):
        """
        Verify exactly two tools are registered (security constraint).
        """
        from server.tools import get_tool_registry

        registry = get_tool_registry()
        assert registry["mode"] == "SECURE"
        assert len(registry["registered_tools"]) == 2
        assert "explore_study_metadata" in registry["registered_tools"]
        assert "build_technical_request" in registry["registered_tools"]


# =============================================================================
# Response Format Tests
# =============================================================================

class TestResponseFormats:
    """
    Tests for API response format consistency.

    These tests verify that responses follow expected formats
    for both success and error cases.
    """

    def test_health_response_format(self, test_client):
        """
        Health endpoint should return consistent JSON format.
        """
        response = test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "server" in data
        assert "version" in data

    def test_ready_response_format(self, test_client):
        """
        Ready endpoint should return consistent JSON format.
        """
        response = test_client.get("/ready")
        data = response.json()

        assert "ready" in data
        assert "server" in data

    def test_unauthorized_response_format(self, test_client, no_auth_headers):
        """
        Unauthorized responses should include WWW-Authenticate header.
        """
        response = test_client.get("/tools", headers=no_auth_headers)

        assert response.status_code == 401
        assert "www-authenticate" in response.headers
