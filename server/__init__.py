"""
RePORTaLiN MCP Server Package.

This package contains the production-ready Model Context Protocol (MCP)
server implementation for the RePORTaLiN clinical data system.

Modules:
    config: Configuration management with Pydantic Settings
    logger: Structured logging with structlog
    auth: Token-based authentication for FastAPI
    tools: MCP tool definitions with Pydantic models
    main: FastAPI application with SSE transport

Public API:
    - get_settings(): Get the application settings singleton
    - get_logger(): Get a structured logger instance
    - configure_logging(): Configure logging (call once at startup)
    - require_auth: FastAPI dependency for required authentication
    - optional_auth: FastAPI dependency for optional authentication
    - AuthContext: Authentication context dataclass
    - mcp: FastMCP server instance with registered tools
    - app: FastAPI application instance
    - run_server(): Start the server with uvicorn

Example:
    >>> from server import get_settings, get_logger, configure_logging
    >>> configure_logging()
    >>> settings = get_settings()
    >>> logger = get_logger(__name__)
    >>> logger.info("Server initialized", port=settings.mcp_port)
    
    # Or run the server directly:
    >>> from server import run_server
    >>> run_server(host="0.0.0.0", port=8000)
"""

from server.config import Settings, get_settings, get_project_root, Environment, LogLevel
from server.logger import (
    configure_logging,
    get_logger,
    bind_context,
    clear_context,
    get_request_id,
    set_request_id,
)
from server.auth import (
    AuthContext,
    require_auth,
    optional_auth,
    verify_token,
    generate_token,
)
from server.tools import mcp, get_tool_registry
from server.main import app, base_app, create_app, create_secured_app, run_server

# Security module exports (lazy import to avoid circular dependencies)
from server.security import (
    AES256GCMCipher,
    RateLimiter,
    RateLimitConfig,
    SecurityHeadersMiddleware,
    InputValidationMiddleware,
    RateLimitMiddleware,
    RotatableSecret,
)

__all__ = [
    # Configuration
    "Settings",
    "get_settings",
    "get_project_root",
    "Environment",
    "LogLevel",
    # Logging
    "configure_logging",
    "get_logger",
    "bind_context",
    "clear_context",
    "get_request_id",
    "set_request_id",
    # Authentication
    "AuthContext",
    "require_auth",
    "optional_auth",
    "verify_token",
    "generate_token",
    # MCP Server
    "mcp",
    "get_tool_registry",
    # FastAPI Application
    "app",
    "base_app",
    "create_app",
    "create_secured_app",
    "run_server",
    # Security
    "AES256GCMCipher",
    "RateLimiter",
    "RateLimitConfig",
    "SecurityHeadersMiddleware",
    "InputValidationMiddleware",
    "RateLimitMiddleware",
    "RotatableSecret",
]
