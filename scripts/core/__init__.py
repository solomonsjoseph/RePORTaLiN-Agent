"""Backward-compatible shim for scripts/core package.

DEPRECATED: Use reportalin.core instead.
This module re-exports symbols from reportalin.core for backward compatibility.
"""
# Settings
from reportalin.core.config import (
    Environment,
    LogLevel,
    Settings,
    get_project_root,
    get_settings,
    reload_settings,
)

# Logging
from reportalin.core.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    get_request_id,
    set_request_id,
)

# Log Decryption
from reportalin.core.log_decryptor import (
    AuthorizationError,
    DecryptionError,
    LogDecryptor,
    generate_keypair,
)

__all__ = [
    "AuthorizationError",
    "DecryptionError",
    "Environment",
    "LogDecryptor",
    "LogLevel",
    "Settings",
    "bind_context",
    "clear_context",
    "configure_logging",
    "generate_keypair",
    "get_logger",
    "get_project_root",
    "get_request_id",
    "get_settings",
    "reload_settings",
    "set_request_id",
]
