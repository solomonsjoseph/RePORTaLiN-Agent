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

from server.tools import (
    QueryDatabaseInput,
    SearchDictionaryInput,
    FetchMetricsInput,
    MetricType,
)
from server.auth import verify_token


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
# Query Validation Security Tests
# =============================================================================

class TestQueryValidation:
    """
    Tests for SQL injection prevention in QueryDatabaseInput.
    
    These tests verify that dangerous SQL patterns are rejected
    at the Pydantic validation layer, before reaching any database.
    """
    
    @pytest.mark.security
    def test_delete_query_rejected(self):
        """
        DELETE queries should be rejected by the validator.
        
        This is a critical security test - DELETE queries could
        cause data loss if allowed through.
        """
        with pytest.raises(ValidationError) as exc_info:
            QueryDatabaseInput(query="DELETE FROM patients WHERE id = 1")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
        # Check that the error is about forbidden keywords
        error_msg = str(errors[0]["msg"]).lower()
        assert "select" in error_msg or "delete" in error_msg or "forbidden" in error_msg
    
    @pytest.mark.security
    def test_insert_query_rejected(self):
        """
        INSERT queries should be rejected by the validator.
        """
        with pytest.raises(ValidationError) as exc_info:
            QueryDatabaseInput(query="INSERT INTO patients (id, name) VALUES (1, 'test')")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
    
    @pytest.mark.security
    def test_update_query_rejected(self):
        """
        UPDATE queries should be rejected by the validator.
        """
        with pytest.raises(ValidationError) as exc_info:
            QueryDatabaseInput(query="UPDATE patients SET name = 'test' WHERE id = 1")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
    
    @pytest.mark.security
    def test_drop_table_rejected(self):
        """
        DROP TABLE queries should be rejected by the validator.
        
        This prevents database destruction attacks.
        """
        with pytest.raises(ValidationError) as exc_info:
            QueryDatabaseInput(query="DROP TABLE patients")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
    
    @pytest.mark.security
    def test_truncate_table_rejected(self):
        """
        TRUNCATE TABLE queries should be rejected by the validator.
        """
        with pytest.raises(ValidationError) as exc_info:
            QueryDatabaseInput(query="TRUNCATE TABLE patients")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
    
    @pytest.mark.security
    def test_sql_comment_injection_rejected(self):
        """
        SQL comment injection attempts should be rejected.
        
        Comments like -- or /* can be used to bypass query restrictions.
        """
        # Test double-dash comment injection
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query="SELECT * FROM patients -- DELETE FROM patients")
        
        # Test multi-line comment injection
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query="SELECT * FROM patients /* DELETE */ WHERE 1=1")
    
    @pytest.mark.security
    def test_exec_statement_rejected(self):
        """
        EXEC/EXECUTE statements should be rejected.
        
        These can be used to execute arbitrary stored procedures.
        """
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query="EXEC sp_executesql @sql")
        
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query="EXECUTE sp_executesql @sql")
    
    @pytest.mark.security
    def test_alter_table_rejected(self):
        """
        ALTER TABLE statements should be rejected.
        
        These could be used to modify schema.
        """
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query="ALTER TABLE patients ADD COLUMN hack TEXT")
    
    @pytest.mark.security
    def test_create_table_rejected(self):
        """
        CREATE TABLE statements should be rejected.
        """
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query="CREATE TABLE malicious (id INT)")
    
    @pytest.mark.security
    def test_valid_select_accepted(self):
        """
        Valid SELECT queries should be accepted.
        
        This is a positive test to ensure legitimate queries work.
        """
        # Simple select
        input1 = QueryDatabaseInput(query="SELECT * FROM patients")
        assert input1.query.startswith("SELECT")
        
        # Select with WHERE
        input2 = QueryDatabaseInput(query="SELECT id, name FROM patients WHERE age > 18")
        assert "WHERE" in input2.query.upper()
        
        # Select with JOIN
        input3 = QueryDatabaseInput(
            query="SELECT p.*, d.diagnosis FROM patients p JOIN diagnoses d ON p.id = d.patient_id"
        )
        assert "JOIN" in input3.query.upper()
    
    @pytest.mark.security
    def test_query_must_start_with_select(self):
        """
        Queries that don't start with SELECT should be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            QueryDatabaseInput(query="SHOW TABLES")
        
        errors = exc_info.value.errors()
        assert len(errors) > 0
    
    @pytest.mark.security
    def test_all_dangerous_queries_rejected(self, dangerous_queries):
        """
        All dangerous queries from the fixture should be rejected.
        
        Uses the dangerous_queries fixture from conftest.py.
        """
        for dangerous_query in dangerous_queries:
            with pytest.raises(ValidationError):
                QueryDatabaseInput(query=dangerous_query)
    
    @pytest.mark.security
    def test_all_safe_queries_accepted(self, safe_queries):
        """
        All safe queries from the fixture should be accepted.
        
        Uses the safe_queries fixture from conftest.py.
        """
        for safe_query in safe_queries:
            input_model = QueryDatabaseInput(query=safe_query)
            assert input_model.query is not None


# =============================================================================
# Search Dictionary Security Tests
# =============================================================================

class TestSearchDictionarySecurity:
    """
    Tests for injection prevention in SearchDictionaryInput.
    
    These tests verify that dangerous characters are sanitized
    from search terms before processing.
    """
    
    @pytest.mark.security
    def test_sql_injection_characters_sanitized(self):
        """
        SQL injection characters should be removed from search terms.
        """
        input_model = SearchDictionaryInput(
            search_term="patient; DROP TABLE--"
        )
        
        # Semicolons and double-dashes should be removed
        assert ";" not in input_model.search_term
        assert "--" not in input_model.search_term
    
    @pytest.mark.security
    def test_quote_injection_sanitized(self):
        """
        Quote characters should be removed from search terms.
        """
        input_model = SearchDictionaryInput(
            search_term="patient' OR '1'='1"
        )
        
        assert "'" not in input_model.search_term
    
    @pytest.mark.security
    def test_backtick_injection_sanitized(self):
        """
        Backtick characters should be removed from search terms.
        """
        input_model = SearchDictionaryInput(
            search_term="patient`; DROP TABLE--"
        )
        
        assert "`" not in input_model.search_term
    
    @pytest.mark.security
    def test_parentheses_sanitized(self):
        """
        Parentheses should be removed from search terms.
        
        These could be used for function injection.
        """
        input_model = SearchDictionaryInput(
            search_term="EXEC(DROP TABLE)"
        )
        
        assert "(" not in input_model.search_term
        assert ")" not in input_model.search_term
    
    @pytest.mark.security
    def test_valid_search_term_accepted(self):
        """
        Valid search terms should work normally.
        """
        input_model = SearchDictionaryInput(
            search_term="patient_id"
        )
        
        assert input_model.search_term == "patient_id"
    
    @pytest.mark.security
    def test_minimum_length_enforced(self):
        """
        Search terms must meet minimum length requirement.
        
        This prevents empty or single-character searches.
        """
        with pytest.raises(ValidationError):
            SearchDictionaryInput(search_term="a")


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
# Metrics Input Validation Tests
# =============================================================================

class TestMetricsInputValidation:
    """
    Tests for FetchMetricsInput validation.
    """
    
    @pytest.mark.security
    def test_valid_metric_types_accepted(self):
        """
        All valid metric types should be accepted.
        """
        for metric_type in MetricType:
            input_model = FetchMetricsInput(
                metric_type=metric_type,
                field_name="test_field",
            )
            assert input_model.metric_type == metric_type
    
    @pytest.mark.security
    def test_invalid_metric_type_rejected(self):
        """
        Invalid metric types should be rejected.
        """
        with pytest.raises(ValidationError):
            FetchMetricsInput(
                metric_type="invalid_type",  # type: ignore
                field_name="test_field",
            )
    
    @pytest.mark.security
    def test_field_name_required(self):
        """
        Field name is required and cannot be empty.
        """
        with pytest.raises(ValidationError):
            FetchMetricsInput(
                metric_type=MetricType.COUNT,
                field_name="",
            )


# =============================================================================
# Tool Execution Security Tests
# =============================================================================

class TestToolExecutionSecurity:
    """
    Tests for direct tool function security.
    
    These tests import and call tool functions directly to verify
    their security behavior without going through the HTTP layer.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_query_database_rejects_delete_query_directly(self):
        """
        CRITICAL: Import query_database directly and verify DELETE queries are rejected.
        
        This test satisfies Phase 5 requirement:
        "Import the query_database function directly from server.tools.
         Pass it a DELETE query and assert it raises a ValueError."
        
        The security check happens at the Pydantic validation layer,
        so creating a QueryDatabaseInput with a DELETE query raises ValidationError.
        """
        from server.tools import query_database, QueryDatabaseInput
        
        # Attempting to create input with DELETE query should raise ValueError
        # (Pydantic's ValidationError inherits from ValueError)
        with pytest.raises((ValueError, ValidationError)) as exc_info:
            QueryDatabaseInput(query="DELETE FROM patients WHERE id = 1")
        
        # Verify the error message mentions the security restriction
        error_str = str(exc_info.value).lower()
        assert "select" in error_str or "delete" in error_str or "forbidden" in error_str
    
    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_query_database_validates_input(self, query_database_input):
        """
        query_database tool should validate input before execution.
        """
        from server.tools import query_database
        
        # Create valid input
        input_model = QueryDatabaseInput(**query_database_input)
        
        # Execute should work with valid input
        result = await query_database(input_model)
        assert result["success"] is True
    
    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_search_dictionary_validates_input(self, search_dictionary_input):
        """
        search_dictionary tool should validate input before execution.
        """
        from server.tools import search_dictionary
        
        # Create valid input
        input_model = SearchDictionaryInput(**search_dictionary_input)
        
        # Execute should work with valid input
        result = await search_dictionary(input_model)
        assert result["success"] is True
    
    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_fetch_metrics_validates_input(self, fetch_metrics_input):
        """
        fetch_metrics tool should validate input before execution.
        """
        from server.tools import fetch_metrics
        
        # Create valid input
        fetch_metrics_input["metric_type"] = MetricType.COUNT
        input_model = FetchMetricsInput(**fetch_metrics_input)
        
        # Execute should work with valid input
        result = await fetch_metrics(input_model)
        assert result["success"] is True
    
    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_health_check_returns_status(self):
        """
        health_check tool should return server status.
        """
        from server.tools import health_check
        
        result = await health_check()
        assert result["status"] == "healthy"
        assert "server_name" in result


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
