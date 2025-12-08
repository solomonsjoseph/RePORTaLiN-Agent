"""
RePORTaLiN-Specialist Core Package.

Centralized configuration, logging, and security modules following modern
Python best practices (2024+).

Modules:
    - ``settings``: Pydantic-based configuration management with env var support
    - ``structured_logging``: Structured logging with JSON output and PHI redaction
    - ``log_decryptor``: Secure log decryption utility for authorized developers

Best Practices Implemented:
    - Type-safe configuration with Pydantic Settings v2
    - Structured logging with contextual information
    - Environment variable support with .env files
    - Automatic PHI/PII redaction in logs
    - RSA/AES hybrid encryption for sensitive logs
    - Key rotation tracking and warnings
    - Developer access controls via key fingerprints

Configuration:
    Settings can be configured via environment variables (REPORTALIN_* prefix)
    or a .env file. See .env.example for available options.

    ::

        # Environment variables
        export REPORTALIN_LOG_LEVEL=DEBUG
        export REPORTALIN_LOG_VERBOSE=true
        export REPORTALIN_MCP_TRANSPORT=stdio

Usage:
    ::

        from scripts.core import get_settings, get_structured_logger, log_context

        # Get validated settings
        settings = get_settings()
        print(f"Log level: {settings.logging.level}")
        print(f"Data directory: {settings.data_dir}")

        # Get structured logger with PHI redaction
        logger = get_structured_logger(__name__)
        logger.info("Processing started", file_count=10)

        # Use context manager for request-scoped logging
        with log_context(request_id="abc123", user="analyst"):
            logger.info("Query executed", query_type="aggregate")

Log Decryption (for authorized developers):
    ::

        # Generate keypair
        python -m scripts.core.log_decryptor --generate-keys

        # Decrypt logs
        python -m scripts.core.log_decryptor encrypted_logs/ --level ERROR

See Also:
    - .env.example - Configuration options
    - docs/MCP_SERVER_SETUP.md - Deployment guide
    - scripts/utils/logging.py - Base logging implementation
    - server/ - MCP server implementation
"""

from .settings import (
    Settings,
    get_settings,
    reload_settings,
    LogLevel,
    TransportMode,
    LoggingSettings,
    EncryptionSettings,
    MCPSettings,
)
from .structured_logging import (
    configure_logging,
    get_structured_logger,
    log_context,
    set_context,
    clear_context,
    StructuredLogger,
    BoundLogger,
    JSONFormatter,
)
from .log_decryptor import (
    LogDecryptor,
    DecryptionError,
    AuthorizationError,
    generate_keypair,
)

__all__ = [
    # Settings
    "Settings",
    "get_settings",
    "reload_settings",
    "LogLevel",
    "TransportMode",
    "LoggingSettings",
    "EncryptionSettings",
    "MCPSettings",
    # Logging
    "configure_logging",
    "get_structured_logger",
    "log_context",
    "set_context",
    "clear_context",
    "StructuredLogger",
    "BoundLogger",
    "JSONFormatter",
    # Log Decryption
    "LogDecryptor",
    "DecryptionError",
    "AuthorizationError",
    "generate_keypair",
]
