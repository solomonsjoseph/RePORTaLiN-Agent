"""
Security Module for RePORTaLiN MCP Server.

This module provides enterprise-grade security components following
Zero Trust principles and 2025 compliance standards (HIPAA, DPDPA, GDPR).

Components:
    - encryption: AES-256-GCM authenticated encryption
    - rate_limiter: Request rate limiting with sliding window
    - middleware: Security headers and input validation
    - secrets: Secrets rotation and management

Design Principles:
    - Defense in depth: Multiple layers of security
    - Zero Trust: Never trust, always verify
    - Fail secure: Deny by default on errors
    - Auditability: Log all security events

Usage:
    >>> from server.security import AES256GCMCipher, RateLimiter
    >>> 
    >>> # Encryption
    >>> cipher = AES256GCMCipher.generate()
    >>> encrypted = cipher.encrypt(b"sensitive data")
    >>> decrypted = cipher.decrypt(encrypted)
    >>> 
    >>> # Rate limiting
    >>> limiter = RateLimiter(requests_per_minute=60)
    >>> if not await limiter.is_allowed(client_id):
    >>>     raise RateLimitExceeded()
"""

from server.security.encryption import (
    AES256GCMCipher,
    EncryptedPayload,
    EncryptionError,
    DecryptionError,
)
from server.security.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    InMemoryRateLimiter,
)
from server.security.middleware import (
    SecurityHeadersMiddleware,
    InputValidationMiddleware,
    RateLimitMiddleware,
)
from server.security.secrets import (
    SecretRotator,
    RotatableSecret,
    SecretValidationResult,
)

__all__ = [
    # Encryption
    "AES256GCMCipher",
    "EncryptedPayload",
    "EncryptionError",
    "DecryptionError",
    # Rate Limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitExceeded",
    "InMemoryRateLimiter",
    # Middleware
    "SecurityHeadersMiddleware",
    "InputValidationMiddleware",
    "RateLimitMiddleware",
    # Secrets
    "SecretRotator",
    "RotatableSecret",
    "SecretValidationResult",
]
