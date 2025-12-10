"""
MCP Server Integration Tests.

These tests verify the complete MCP server setup including:
- Server imports and initialization
- Tool registration and schemas
- HTTP endpoint authentication
- SSE transport connection

Run with: pytest tests/integration/test_server_startup.py -v
"""

import pytest
from httpx import ASGITransport, AsyncClient

# Test token - must match conftest.py
TEST_AUTH_TOKEN = "test-secret-token-12345"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.mcp,
    pytest.mark.asyncio,
]


# =============================================================================
# Fixture for properly configured app with auth
# =============================================================================

@pytest.fixture
def configured_app(monkeypatch):
    """
    Get the FastAPI application with proper auth configuration.

    This fixture ensures:
    1. MCP_AUTH_TOKEN is set BEFORE importing server modules
    2. All caches are cleared so auth is properly configured
    """
    # Set environment BEFORE any imports
    monkeypatch.setenv("MCP_AUTH_TOKEN", TEST_AUTH_TOKEN)
    monkeypatch.setenv("MCP_AUTH_ENABLED", "true")
    monkeypatch.setenv("ENVIRONMENT", "local")

    # Clear all caches
    from server.config import get_settings
    get_settings.cache_clear()

    from server.auth import get_rotatable_secret
    get_rotatable_secret.cache_clear()

    # Now import and return the app
    from server.main import base_app
    return base_app


# =============================================================================
# Server Import Tests
# =============================================================================

def test_server_import():
    """Test that the server modules can be imported."""
    from server import (
        app,
        mcp,
    )
    assert app is not None
    assert mcp is not None


def test_settings_load():
    """Test that settings load correctly."""
    from server.config import get_settings
    settings = get_settings()
    assert settings.mcp_host is not None
    assert settings.mcp_port > 0
    assert settings.environment is not None


# =============================================================================
# Tool Registration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_tools_registered():
    """Test that all expected tools are registered (10 tools total).
    
    Tool Selection Guide:
    - combined_search: DEFAULT for ALL queries (searches ALL data sources)
    - search_data_dictionary: ONLY for variable definitions (no statistics)
    """
    from server.tools import mcp
    tools = await mcp.list_tools()

    tool_names = [t.name for t in tools]

    # Verify the 10 secure tools exist
    # Primary tools
    assert "combined_search" in tool_names  # DEFAULT for all queries
    assert "natural_language_query" in tool_names
    assert "cohort_summary" in tool_names
    assert "cross_tabulation" in tool_names
    # Detailed analysis tools
    assert "variable_details" in tool_names
    assert "data_quality_report" in tool_names
    assert "multi_variable_comparison" in tool_names
    # Supporting tools
    assert "search_data_dictionary" in tool_names  # Variable definitions ONLY
    assert "search_cleaned_dataset" in tool_names
    assert "search_original_dataset" in tool_names

    # Verify old tools are NOT present (security check)
    assert "query_database" not in tool_names
    assert "search_dictionary" not in tool_names
    assert "fetch_metrics" not in tool_names
    assert "list_datasets" not in tool_names
    assert "describe_schema" not in tool_names
    assert "explore_study_metadata" not in tool_names
    assert "build_technical_request" not in tool_names
    assert "health_check" not in tool_names

    # Verify we have exactly 10 tools
    assert len(tool_names) == 10


@pytest.mark.asyncio
async def test_tool_schemas():
    """Test that all tools have valid JSON schemas."""
    from server.tools import mcp
    tools = await mcp.list_tools()

    for tool in tools:
        # Every tool should have a name
        assert tool.name is not None
        assert len(tool.name) > 0

        # Every tool should have a description (for LLM selection)
        assert tool.description is not None
        assert len(tool.description) > 10  # Should be descriptive

        # Input schema should be valid JSON schema
        if tool.inputSchema:
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"


def test_tool_registry():
    """Test the tool registry utility."""
    from server.tools import get_tool_registry
    from shared.constants import SERVER_NAME, SERVER_VERSION

    registry = get_tool_registry()

    assert registry["server_name"] == SERVER_NAME
    assert registry["version"] == SERVER_VERSION
    assert len(registry["registered_tools"]) >= 4


# =============================================================================
# HTTP Endpoint Tests (using configured_app fixture)
# =============================================================================

@pytest.mark.asyncio
async def test_health_endpoint(configured_app):
    """Test health check endpoint (no auth required)."""
    from shared.constants import SERVER_NAME

    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["server"] == SERVER_NAME


@pytest.mark.asyncio
async def test_ready_endpoint(configured_app):
    """Test readiness check endpoint (no auth required)."""
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True


@pytest.mark.asyncio
async def test_tools_endpoint_requires_auth(configured_app):
    """Test that /tools endpoint requires authentication."""
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.get("/tools")

        # Should fail without auth
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_tools_endpoint_with_auth(configured_app):
    """Test /tools endpoint with valid authentication."""
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.get(
            "/tools",
            headers={"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) >= 4


# =============================================================================
# SSE Transport Tests
# =============================================================================

@pytest.mark.asyncio
async def test_mcp_sse_requires_auth(configured_app):
    """Test that MCP SSE endpoint requires authentication."""
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.get("/mcp/sse")

        # Should fail without auth
        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.skip(reason="SSE streaming test hangs in CI - test manually")
async def test_mcp_sse_with_auth(configured_app):
    """Test MCP SSE endpoint returns 200 with valid authentication."""
    # Use a simple HEAD-like request to verify auth passes
    # Full SSE streaming is tested manually
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000", timeout=2.0) as client:
        # Just verify auth middleware passes the request through
        # The SSE endpoint will start streaming, but we don't need to consume it
        try:
            async with client.stream(
                "GET",
                "/mcp/sse",
                headers={"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}
            ) as response:
                # If we get here without 401, auth passed
                assert response.status_code == 200
                # Verify it's an SSE response
                content_type = response.headers.get("content-type", "")
                assert "text/event-stream" in content_type
        except Exception as e:
            # httpx may raise on disconnect, but if we got past auth that's fine
            if "401" in str(e):
                pytest.fail("Authentication failed")
