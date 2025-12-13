"""
Unit tests for rate limiter module.

Tests cover:
- Token bucket algorithm
- Rate limit enforcement
- Configuration options
"""

from __future__ import annotations

import asyncio

import pytest

from server.security.rate_limiter import RateLimitConfig, RateLimiter


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RateLimitConfig()

        assert config.requests_per_second > 0
        assert config.burst_size > 0

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests_per_second=100.0,
            burst_size=200,
        )

        assert config.requests_per_second == 100.0
        assert config.burst_size == 200


class TestRateLimiter:
    """Tests for RateLimiter token bucket implementation."""

    @pytest.fixture
    def limiter(self) -> RateLimiter:
        """Create a rate limiter for testing."""
        config = RateLimitConfig(
            requests_per_second=10.0,
            burst_size=5,
        )
        return RateLimiter(config)

    @pytest.mark.asyncio
    async def test_allows_initial_requests(self, limiter: RateLimiter) -> None:
        """Test that initial requests up to burst size are allowed."""
        client_id = "test-client-1"

        # Should allow burst_size requests
        for _ in range(5):
            allowed = await limiter.is_allowed(client_id)
            assert allowed is True

    @pytest.mark.asyncio
    async def test_blocks_after_burst(self, limiter: RateLimiter) -> None:
        """Test that requests are blocked after burst is exhausted."""
        client_id = "test-client-2"

        # Exhaust the burst
        for _ in range(5):
            await limiter.is_allowed(client_id)

        # Next request should be blocked
        allowed = await limiter.is_allowed(client_id)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_tokens_replenish(self, limiter: RateLimiter) -> None:
        """Test that tokens replenish over time."""
        client_id = "test-client-3"

        # Exhaust the burst
        for _ in range(5):
            await limiter.is_allowed(client_id)

        # Wait for token replenishment (1 token per 0.1 seconds at 10 req/sec)
        await asyncio.sleep(0.15)

        # Should have at least 1 token now
        allowed = await limiter.is_allowed(client_id)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_separate_limits_per_client(self, limiter: RateLimiter) -> None:
        """Test that each client has separate rate limit."""
        client1 = "client-1"
        client2 = "client-2"

        # Exhaust client1's burst
        for _ in range(5):
            await limiter.is_allowed(client1)

        # client2 should still have tokens
        allowed = await limiter.is_allowed(client2)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_get_remaining_tokens(self, limiter: RateLimiter) -> None:
        """Test getting remaining tokens for a client."""
        client_id = "test-client-4"

        # Use some tokens
        await limiter.is_allowed(client_id)
        await limiter.is_allowed(client_id)

        remaining = await limiter.get_remaining_tokens(client_id)
        assert remaining <= 3  # Started with 5, used 2

    @pytest.mark.asyncio
    async def test_reset_client(self, limiter: RateLimiter) -> None:
        """Test resetting a client's rate limit."""
        client_id = "test-client-5"

        # Exhaust tokens
        for _ in range(5):
            await limiter.is_allowed(client_id)

        # Reset
        await limiter.reset_client(client_id)

        # Should have tokens again
        allowed = await limiter.is_allowed(client_id)
        assert allowed is True
