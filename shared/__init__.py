"""
RePORTaLiN Shared Types and Schemas Package.

This package contains shared type definitions, Pydantic models, and
JSON schemas used across the server and client implementations.

Modules:
    - types: Core type definitions (ToolResult, TransportType, etc.)
    - constants: Shared constants and configuration defaults
    - schemas: JSON Schema definitions (Draft-7) [Future]
    - models: Pydantic model definitions [Future]
"""

from shared.constants import (
    SERVER_NAME,
    SERVER_VERSION,
    PROTOCOL_VERSION,
    DEFAULT_TRANSPORT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    MIN_K_ANONYMITY,
    DATA_DICTIONARY_PATH,
    ENCRYPTED_LOGS_PATH,
    SSE_KEEPALIVE_INTERVAL,
    DEFAULT_RATE_LIMIT_RPM,
    DEFAULT_RATE_LIMIT_BURST,
    TOKEN_ROTATION_GRACE_PERIOD_SECONDS,
    ENCRYPTION_KEY_ROTATION_DAYS,
)
from shared.types import (
    JsonValue,
    JsonPrimitive,
    JsonArray,
    JsonObject,
    TransportType,
    LogLevel,
    ToolResult,
    PrivacyMode,
    EnvironmentType,
    ServerCapabilities,
    SecurityContext,
    ToolName,
    ResourceUri,
    PromptId,
    SessionId,
)

__all__ = [
    # Constants
    "SERVER_NAME",
    "SERVER_VERSION",
    "PROTOCOL_VERSION",
    "DEFAULT_TRANSPORT",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "MIN_K_ANONYMITY",
    "DATA_DICTIONARY_PATH",
    "ENCRYPTED_LOGS_PATH",
    "SSE_KEEPALIVE_INTERVAL",
    "DEFAULT_RATE_LIMIT_RPM",
    "DEFAULT_RATE_LIMIT_BURST",
    "TOKEN_ROTATION_GRACE_PERIOD_SECONDS",
    "ENCRYPTION_KEY_ROTATION_DAYS",
    # Types
    "JsonValue",
    "JsonPrimitive",
    "JsonArray",
    "JsonObject",
    "TransportType",
    "LogLevel",
    "ToolResult",
    "PrivacyMode",
    "EnvironmentType",
    "ServerCapabilities",
    "SecurityContext",
    "ToolName",
    "ResourceUri",
    "PromptId",
    "SessionId",
]
