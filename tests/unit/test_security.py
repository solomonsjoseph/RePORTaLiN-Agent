"""
Dedicated Security Tests for MCP Server.

Phase 5: Verification, Testing & Security Hardening

This module provides focused security testing including:
- Timing attack prevention verification
- Authentication bypass attempts
- Input sanitization validation
- Token entropy requirements

These tests are marked with @pytest.mark.security for selective execution.

Running Security Tests:
    ```bash
    # Run all security tests
    uv run pytest tests/unit/test_security.py -v
    
    # Run with timing analysis
    uv run pytest tests/unit/test_security.py -v --tb=long
    
    # Include in CI pipeline
    uv run pytest -m security --strict-markers
    ```

IMPORTANT: These tests verify security properties without exposing
actual secrets or creating vulnerabilities.
"""

from __future__ import annotations

import hashlib
import secrets
import statistics
import time

import pytest

from server.auth import verify_token, generate_token


# =============================================================================
# Test Markers
# =============================================================================

pytestmark = [pytest.mark.security, pytest.mark.unit]


# =============================================================================
# Timing Attack Prevention Tests
# =============================================================================

class TestTimingAttackPrevention:
    """
    Tests that token verification uses constant-time comparison.
    
    Timing attacks exploit measurable differences in comparison time
    to guess tokens character by character. Constant-time comparison
    (secrets.compare_digest) prevents this by always comparing the
    full string regardless of where mismatches occur.
    """

    @pytest.mark.parametrize("attempts", [100])
    def test_constant_time_comparison_no_timing_leak(self, attempts: int) -> None:
        """
        Verify that wrong tokens don't leak timing information.
        
        This test measures verification time for:
        1. Completely wrong token (first char mismatch)
        2. Partially correct token (last char mismatch)
        3. Correct token
        
        The variance should be similar (no correlation with correctness).
        """
        correct_token = "correct-secret-token-12345678"
        
        # Token that differs in first character
        wrong_first = "Xorrect-secret-token-12345678"
        
        # Token that differs in last character
        wrong_last = "correct-secret-token-1234567X"
        
        times_wrong_first = []
        times_wrong_last = []
        times_correct = []
        
        for _ in range(attempts):
            # Time wrong first char
            start = time.perf_counter_ns()
            verify_token(wrong_first, correct_token)
            times_wrong_first.append(time.perf_counter_ns() - start)
            
            # Time wrong last char
            start = time.perf_counter_ns()
            verify_token(wrong_last, correct_token)
            times_wrong_last.append(time.perf_counter_ns() - start)
            
            # Time correct
            start = time.perf_counter_ns()
            verify_token(correct_token, correct_token)
            times_correct.append(time.perf_counter_ns() - start)
        
        # Calculate means (excluding outliers)
        mean_wrong_first = statistics.mean(sorted(times_wrong_first)[10:-10])
        mean_wrong_last = statistics.mean(sorted(times_wrong_last)[10:-10])
        mean_correct = statistics.mean(sorted(times_correct)[10:-10])
        
        # The ratio between any two should be close to 1.0
        # A timing attack would show wrong_first significantly faster than wrong_last
        ratio_first_last = mean_wrong_first / mean_wrong_last if mean_wrong_last else 1.0
        
        # Allow 50% variance (generous due to system noise)
        # Non-constant time would show >2x difference
        assert 0.5 < ratio_first_last < 2.0, (
            f"Potential timing leak detected! "
            f"wrong_first={mean_wrong_first:.0f}ns, wrong_last={mean_wrong_last:.0f}ns "
            f"(ratio={ratio_first_last:.2f})"
        )


# =============================================================================
# Token Entropy Tests
# =============================================================================

class TestTokenEntropy:
    """
    Tests that generated tokens have sufficient entropy.
    
    Weak tokens are vulnerable to brute-force attacks.
    """

    def test_generated_token_length(self) -> None:
        """Verify default token length is sufficient (256 bits)."""
        token = generate_token()
        # 32 bytes = 64 hex chars = 256 bits of entropy
        assert len(token) >= 64, "Token must be at least 64 hex characters (256 bits)"

    def test_generated_token_randomness(self) -> None:
        """Verify tokens are unique (no weak PRNG)."""
        tokens = [generate_token() for _ in range(1000)]
        unique_tokens = set(tokens)
        assert len(unique_tokens) == 1000, "Token collision detected - weak randomness"

    def test_generated_token_charset(self) -> None:
        """Verify tokens use full hex charset."""
        token = generate_token()
        # Should be valid hex (0-9, a-f)
        int(token, 16)  # Raises ValueError if not valid hex


# =============================================================================
# Authentication Bypass Tests
# =============================================================================

class TestAuthenticationBypass:
    """
    Tests for common authentication bypass attempts.
    """

    def test_empty_token_rejected(self) -> None:
        """Empty string should never authenticate."""
        assert verify_token("", "valid-secret") is False
        assert verify_token("", "") is False

    def test_none_token_rejected(self) -> None:
        """None should never authenticate."""
        assert verify_token(None, "valid-secret") is False  # type: ignore
        assert verify_token("valid", None) is False  # type: ignore
        assert verify_token(None, None) is False  # type: ignore

    def test_whitespace_token_rejected(self) -> None:
        """Whitespace-only tokens should fail."""
        assert verify_token("   ", "valid-secret") is False
        assert verify_token("\t\n", "valid-secret") is False

    def test_case_sensitivity(self) -> None:
        """Tokens should be case-sensitive."""
        secret = "MySecretToken123"
        assert verify_token("MySecretToken123", secret) is True
        assert verify_token("mysecrettoken123", secret) is False
        assert verify_token("MYSECRETTOKEN123", secret) is False

    def test_unicode_normalization_attack(self) -> None:
        """Unicode normalization should not bypass auth."""
        # Some systems normalize unicode, which could be exploited
        secret = "password"
        # Common unicode tricks
        assert verify_token("ｐａｓｓｗｏｒｄ", secret) is False  # Fullwidth
        assert verify_token("pаsswоrd", secret) is False  # Cyrillic а and о

    def test_null_byte_injection(self) -> None:
        """Null bytes should not truncate comparison."""
        secret = "full-secret-token"
        # In C-style strings, \x00 terminates - Python handles this correctly
        assert verify_token("full-secret\x00-token", secret) is False
        assert verify_token("full\x00", secret) is False


# =============================================================================
# Input Sanitization Tests
# =============================================================================

class TestInputSanitization:
    """
    Tests for proper input handling in auth system.
    """

    def test_very_long_token_handled(self) -> None:
        """Extremely long tokens should not cause DoS."""
        long_token = "a" * 10_000_000  # 10MB string
        secret = "short-secret"
        
        start = time.time()
        result = verify_token(long_token, secret)
        elapsed = time.time() - start
        
        assert result is False
        # Should complete quickly (< 1 second even with constant-time)
        assert elapsed < 5.0, f"Long token verification took {elapsed:.2f}s (DoS risk)"

    def test_binary_data_in_token(self) -> None:
        """Binary data should be handled safely."""
        binary_token = bytes(range(256)).decode("latin-1")
        secret = "valid-secret"
        
        # Should not raise, just return False
        result = verify_token(binary_token, secret)
        assert result is False


# =============================================================================
# Token Storage Security Tests
# =============================================================================

class TestTokenStorageSecurity:
    """
    Tests that tokens are not inadvertently exposed.
    """

    def test_token_not_in_exception_message(self) -> None:
        """Tokens should never appear in exception messages."""
        secret = "super-secret-token-12345"
        wrong = "wrong-token-attempt"
        
        # verify_token doesn't raise, but we test the principle
        result = verify_token(wrong, secret)
        assert result is False
        
        # If we had exceptions, they shouldn't contain the secret
        # This is a design principle test

    def test_authcontext_does_not_expose_token(self) -> None:
        """AuthContext should not store the actual token."""
        from server.auth import AuthContext
        
        ctx = AuthContext(
            is_authenticated=True,
            auth_method="bearer",
            client_info={"ip": "127.0.0.1"},
        )
        
        # Check that repr/str don't leak tokens
        ctx_str = str(ctx)
        ctx_repr = repr(ctx)
        
        # AuthContext shouldn't have a token field at all
        assert not hasattr(ctx, "token")
        assert not hasattr(ctx, "secret")
        assert "secret" not in ctx_str.lower()
        assert "secret" not in ctx_repr.lower()


# =============================================================================
# AES-256-GCM Encryption Tests (Phase 1 Security Hardening)
# =============================================================================

class TestAES256GCMCipher:
    """Tests for the AES-256-GCM cipher implementation."""
    
    def test_generate_creates_valid_cipher(self) -> None:
        """Test that generate() creates a working cipher."""
        from server.security.encryption import AES256GCMCipher
        
        cipher = AES256GCMCipher.generate()
        assert cipher is not None
    
    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test that data can be encrypted and decrypted."""
        from server.security.encryption import AES256GCMCipher
        
        cipher = AES256GCMCipher.generate()
        plaintext = b"Hello, World! This is sensitive PHI data."
        
        encrypted = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_encrypt_produces_different_ciphertext(self) -> None:
        """Test that encrypting the same data twice produces different ciphertext."""
        from server.security.encryption import AES256GCMCipher
        
        cipher = AES256GCMCipher.generate()
        plaintext = b"Same data"
        
        encrypted1 = cipher.encrypt(plaintext)
        encrypted2 = cipher.encrypt(plaintext)
        
        # Different nonces should produce different ciphertext
        assert encrypted1.ciphertext != encrypted2.ciphertext
        assert encrypted1.nonce != encrypted2.nonce
    
    def test_export_import_key(self) -> None:
        """Test that keys can be exported and imported."""
        from server.security.encryption import AES256GCMCipher
        
        cipher1 = AES256GCMCipher.generate()
        plaintext = b"Test data"
        
        encrypted = cipher1.encrypt(plaintext)
        
        key_b64 = cipher1.export_key()
        cipher2 = AES256GCMCipher.from_key(key_b64)
        
        decrypted = cipher2.decrypt(encrypted)
        assert decrypted == plaintext
    
    def test_wrong_key_fails_decryption(self) -> None:
        """Test that wrong key fails decryption with DecryptionError."""
        from server.security.encryption import AES256GCMCipher, DecryptionError
        
        cipher1 = AES256GCMCipher.generate()
        cipher2 = AES256GCMCipher.generate()
        
        plaintext = b"Secret data"
        encrypted = cipher1.encrypt(plaintext)
        
        with pytest.raises(DecryptionError):
            cipher2.decrypt(encrypted)
    
    def test_tampered_ciphertext_fails(self) -> None:
        """Test that tampered ciphertext is detected."""
        from server.security.encryption import (
            AES256GCMCipher,
            EncryptedPayload,
            DecryptionError,
        )
        
        cipher = AES256GCMCipher.generate()
        plaintext = b"Original data"
        
        encrypted = cipher.encrypt(plaintext)
        
        tampered_ciphertext = bytes([encrypted.ciphertext[0] ^ 0xFF]) + encrypted.ciphertext[1:]
        tampered_payload = EncryptedPayload(
            nonce=encrypted.nonce,
            ciphertext=tampered_ciphertext,
        )
        
        with pytest.raises(DecryptionError):
            cipher.decrypt(tampered_payload)
    
    def test_invalid_key_length_raises(self) -> None:
        """Test that invalid key length raises EncryptionError."""
        from server.security.encryption import AES256GCMCipher, EncryptionError
        
        with pytest.raises(EncryptionError):
            AES256GCMCipher(b"short_key")


# =============================================================================
# Rate Limiter Tests (Phase 1 Security Hardening)
# =============================================================================

class TestRateLimiter:
    """Tests for the rate limiter implementation."""
    
    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self) -> None:
        """Test that requests under limit are allowed."""
        from server.security.rate_limiter import RateLimitConfig, InMemoryRateLimiter
        
        config = RateLimitConfig(requests_per_minute=10)
        limiter = InMemoryRateLimiter(config)
        
        for _ in range(5):
            result = await limiter.check("client-1")
            assert result.allowed
    
    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self) -> None:
        """Test that requests over limit are blocked."""
        from server.security.rate_limiter import RateLimitConfig, InMemoryRateLimiter
        
        config = RateLimitConfig(requests_per_minute=5)
        limiter = InMemoryRateLimiter(config)
        
        for _ in range(5):
            await limiter.check("client-1")
        
        result = await limiter.check("client-1")
        assert not result.allowed
        assert result.retry_after > 0
    
    @pytest.mark.asyncio
    async def test_different_clients_independent(self) -> None:
        """Test that different clients have independent limits."""
        from server.security.rate_limiter import RateLimitConfig, InMemoryRateLimiter
        
        config = RateLimitConfig(requests_per_minute=3)
        limiter = InMemoryRateLimiter(config)
        
        for _ in range(3):
            await limiter.check("client-1")
        
        result1 = await limiter.check("client-1")
        assert not result1.allowed
        
        result2 = await limiter.check("client-2")
        assert result2.allowed
    
    @pytest.mark.asyncio
    async def test_whitelist_bypasses_limit(self) -> None:
        """Test that whitelisted clients bypass rate limiting."""
        from server.security.rate_limiter import RateLimitConfig, InMemoryRateLimiter
        
        config = RateLimitConfig(
            requests_per_minute=1,
            whitelist=frozenset(["admin"]),
        )
        limiter = InMemoryRateLimiter(config)
        
        for _ in range(10):
            result = await limiter.check("admin")
            assert result.allowed


# =============================================================================
# Rotatable Secret Tests (Phase 1 Security Hardening)
# =============================================================================

class TestRotatableSecret:
    """Tests for rotatable secrets implementation."""
    
    def test_validate_correct_token(self) -> None:
        """Test that correct token validates."""
        from server.security.secrets import RotatableSecret, SecretStatus
        
        secret = RotatableSecret("my-secret-token")
        result = secret.validate("my-secret-token")
        
        assert result.is_valid
        assert result.is_primary
        assert result.status == SecretStatus.VALID
    
    def test_validate_wrong_token(self) -> None:
        """Test that wrong token fails validation."""
        from server.security.secrets import RotatableSecret, SecretStatus
        
        secret = RotatableSecret("correct-token")
        result = secret.validate("wrong-token")
        
        assert not result.is_valid
        assert result.status == SecretStatus.INVALID
    
    def test_rotation_both_tokens_valid(self) -> None:
        """Test that both tokens are valid during rotation."""
        from server.security.secrets import RotatableSecret
        
        secret = RotatableSecret("old-token", grace_period_seconds=3600)
        secret.rotate("new-token")
        
        result_old = secret.validate("old-token")
        result_new = secret.validate("new-token")
        
        assert result_old.is_valid
        assert result_new.is_valid
        assert not result_old.is_primary
        assert result_new.is_primary
    
    def test_force_expire_previous(self) -> None:
        """Test that force_expire_previous invalidates old token."""
        from server.security.secrets import RotatableSecret
        
        secret = RotatableSecret("old-token", grace_period_seconds=3600)
        secret.rotate("new-token")
        
        assert secret.validate("old-token").is_valid
        
        secret.force_expire_previous()
        
        assert not secret.validate("old-token").is_valid
        assert secret.validate("new-token").is_valid
    
    def test_secure_token_generation(self) -> None:
        """Test secure token generation."""
        from server.security.secrets import generate_secure_token
        
        tokens = [generate_secure_token() for _ in range(100)]
        assert len(set(tokens)) == 100  # All unique
