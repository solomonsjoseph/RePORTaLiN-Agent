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
    DATA_DICTIONARY_PATH,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_RATE_LIMIT_BURST,
    DEFAULT_RATE_LIMIT_RPM,
    DEFAULT_TRANSPORT,
    ENCRYPTED_LOGS_PATH,
    ENCRYPTION_KEY_ROTATION_DAYS,
    MIN_K_ANONYMITY,
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    SSE_KEEPALIVE_INTERVAL,
    TOKEN_ROTATION_GRACE_PERIOD_SECONDS,
)
from shared.types import (
    EnvironmentType,
    JsonArray,
    JsonObject,
    JsonPrimitive,
    JsonValue,
    LogLevel,
    PrivacyMode,
    PromptId,
    ResourceUri,
    SecurityContext,
    ServerCapabilities,
    SessionId,
    ToolName,
    ToolResult,
    TransportType,
)

__all__ = [
    "DATA_DICTIONARY_PATH",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_RATE_LIMIT_BURST",
    "DEFAULT_RATE_LIMIT_RPM",
    "DEFAULT_TRANSPORT",
    "ENCRYPTED_LOGS_PATH",
    "ENCRYPTION_KEY_ROTATION_DAYS",
    "MIN_K_ANONYMITY",
    "PROTOCOL_VERSION",
    # Constants
    "SERVER_NAME",
    "SERVER_VERSION",
    "SSE_KEEPALIVE_INTERVAL",
    "TOKEN_ROTATION_GRACE_PERIOD_SECONDS",
    "EnvironmentType",
    "JsonArray",
    "JsonObject",
    "JsonPrimitive",
    # Types
    "JsonValue",
    "LogLevel",
    "PrivacyMode",
    "PromptId",
    "ResourceUri",
    "SecurityContext",
    "ServerCapabilities",
    "SessionId",
    "ToolName",
    "ToolResult",
    "TransportType",
]
