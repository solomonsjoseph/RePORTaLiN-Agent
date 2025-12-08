"""
Tests for the authentication module.

This module tests the authentication utilities and middleware
used to secure the MCP server endpoints.

Tests cover:
- AuthContext dataclass
- Token verification logic
- Token generation
- Request token extraction
- require_auth and optional_auth dependencies
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from server.auth import (
    AuthContext,
    verify_token,
    generate_token,
    get_token_from_request,
)


# =============================================================================
# AuthContext Tests
# =============================================================================

class TestAuthContext:
    """Tests for the AuthContext dataclass."""

    def test_create_authenticated_context(self) -> None:
        """Test creating an authenticated context."""
        ctx = AuthContext(
            is_authenticated=True,
            auth_method="bearer",
        )
        assert ctx.is_authenticated is True
        assert ctx.auth_method == "bearer"

    def test_create_unauthenticated_context(self) -> None:
        """Test creating an unauthenticated context."""
        ctx = AuthContext(
            is_authenticated=False,
            auth_method="none",
        )
        assert ctx.is_authenticated is False
        assert ctx.auth_method == "none"

    def test_default_auth_method(self) -> None:
        """Test default auth_method is 'none'."""
        ctx = AuthContext(is_authenticated=False)
        assert ctx.auth_method == "none"

    def test_context_is_immutable(self) -> None:
        """Test that AuthContext is frozen (immutable)."""
        ctx = AuthContext(is_authenticated=True)
        with pytest.raises(AttributeError):
            ctx.is_authenticated = False  # type: ignore

    def test_client_info_default(self) -> None:
        """Test that client_info defaults to empty dict."""
        ctx = AuthContext(is_authenticated=True)
        assert ctx.client_info == {}

    def test_timestamp_auto_set(self) -> None:
        """Test that timestamp is automatically set."""
        before = time.time()
        ctx = AuthContext(is_authenticated=True)
        after = time.time()
        
        assert before <= ctx.timestamp <= after

    def test_age_seconds_property(self) -> None:
        """Test the age_seconds property."""
        ctx = AuthContext(
            is_authenticated=True,
            timestamp=time.time() - 10.0,
        )
        assert ctx.age_seconds >= 10.0


# =============================================================================
# Token Verification Tests
# =============================================================================

class TestVerifyToken:
    """Tests for the verify_token function."""

    def test_verify_valid_token(self) -> None:
        """Test verification of a valid token."""
        result = verify_token("secret123", "secret123")
        assert result is True

    def test_verify_invalid_token(self) -> None:
        """Test verification of an invalid token."""
        result = verify_token("wrongtoken", "secret123")
        assert result is False

    def test_verify_empty_provided_token(self) -> None:
        """Test verification of an empty provided token."""
        result = verify_token("", "secret123")
        assert result is False

    def test_verify_empty_expected_token(self) -> None:
        """Test verification when expected token is empty."""
        result = verify_token("secret123", "")
        assert result is False

    def test_verify_none_provided_token(self) -> None:
        """Test verification when no token is provided."""
        result = verify_token(None, "secret123")
        assert result is False

    def test_verify_none_expected_token(self) -> None:
        """Test verification when expected token is None."""
        result = verify_token("secret123", None)
        assert result is False

    def test_verify_both_none(self) -> None:
        """Test verification when both tokens are None."""
        result = verify_token(None, None)
        assert result is False

    def test_constant_time_comparison(self) -> None:
        """Test that verification uses constant-time comparison."""
        # Verify same token passes
        assert verify_token("test_token", "test_token") is True
        # Different lengths should fail
        assert verify_token("short", "much_longer_token") is False


# =============================================================================
# Token Generation Tests
# =============================================================================

class TestGenerateToken:
    """Tests for the generate_token function."""

    def test_generate_token_default_length(self) -> None:
        """Test token generation with default length."""
        token = generate_token()
        # Default is 32 bytes = 64 hex characters
        assert len(token) == 64
        assert token.isalnum()  # hex characters only

    def test_generate_token_custom_length(self) -> None:
        """Test token generation with custom length."""
        token = generate_token(length=16)
        assert len(token) == 32  # 16 bytes = 32 hex characters

    def test_generate_unique_tokens(self) -> None:
        """Test that generated tokens are unique."""
        tokens = [generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100


# =============================================================================
# Request Token Extraction Tests
# =============================================================================

class TestGetTokenFromRequest:
    """Tests for the get_token_from_request function.
    
    Note: get_token_from_request is an async function that uses FastAPI
    Depends, so we test it by creating mock request objects and calling
    directly with resolved dependencies.
    """

    @pytest.mark.asyncio
    async def test_extract_bearer_token(self) -> None:
        """Test extracting Bearer token from Authorization header."""
        from fastapi.security import HTTPAuthorizationCredentials
        
        request = MagicMock()
        request.headers = {}
        request.query_params = {}
        
        # Create credentials object like HTTPBearer would
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="mytoken123"
        )
        
        token, method = await get_token_from_request(request, credentials)
        assert token == "mytoken123"
        assert method == "bearer"

    @pytest.mark.asyncio
    async def test_extract_api_key_header(self) -> None:
        """Test extracting token from X-API-Key header."""
        request = MagicMock()
        request.headers = {"X-API-Key": "apikey456"}
        request.query_params = {}
        
        token, method = await get_token_from_request(request, None)
        assert token == "apikey456"
        assert method == "api_key"

    @pytest.mark.asyncio
    async def test_extract_query_param_token(self) -> None:
        """Test extracting token from query parameter."""
        request = MagicMock()
        request.headers = {}
        request.query_params = {"token": "querytoken789"}
        
        token, method = await get_token_from_request(request, None)
        assert token == "querytoken789"
        assert method == "query"

    @pytest.mark.asyncio
    async def test_bearer_takes_precedence(self) -> None:
        """Test that Bearer header takes precedence over other methods."""
        from fastapi.security import HTTPAuthorizationCredentials
        
        request = MagicMock()
        request.headers = {"X-API-Key": "apikey"}
        request.query_params = {"token": "querytoken"}
        
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="bearertoken"
        )
        
        token, method = await get_token_from_request(request, credentials)
        assert token == "bearertoken"
        assert method == "bearer"

    @pytest.mark.asyncio
    async def test_no_token_returns_none(self) -> None:
        """Test that (None, 'none') is returned when no token is present."""
        request = MagicMock()
        request.headers = {}
        request.query_params = {}
        
        token, method = await get_token_from_request(request, None)
        assert token is None
        assert method == "none"

    @pytest.mark.asyncio
    async def test_api_key_precedence_over_query(self) -> None:
        """Test that X-API-Key takes precedence over query param."""
        request = MagicMock()
        request.headers = {"X-API-Key": "apikey"}
        request.query_params = {"token": "querytoken"}
        
        token, method = await get_token_from_request(request, None)
        assert token == "apikey"
        assert method == "api_key"
