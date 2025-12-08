"""
RePORTaLiN MCP Server Entry Point.

This module provides the main entry point for the MCP server.
It handles:
  - Command line argument parsing
  - Transport selection (stdio/http/sse)
  - Signal handling for graceful shutdown
  - Server startup with uvicorn

Usage:
    # Run HTTP/SSE server (default)
    uv run python -m server
    
    # Run with specific options
    uv run python -m server --host 0.0.0.0 --port 8000 --reload
    
    # Or via uvicorn directly
    uv run uvicorn server.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import sys

from server.config import get_settings
from server.logger import configure_logging, get_logger


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="reportalin-mcp",
        description="RePORTaLiN MCP Server - Clinical Data Query System",
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Server bind host (default from MCP_HOST env var)",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server bind port (default from MCP_PORT env var)",
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit",
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the RePORTaLiN MCP server.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse command line arguments
    args = parse_args()
    
    # Handle version flag
    if args.version:
        from shared.constants import SERVER_NAME, SERVER_VERSION, PROTOCOL_VERSION
        print(f"{SERVER_NAME} v{SERVER_VERSION}")
        print(f"MCP Protocol: {PROTOCOL_VERSION}")
        return 0
    
    # Configure logging
    configure_logging()
    logger = get_logger(__name__)
    
    # Get settings
    settings = get_settings()
    
    logger.info(
        "Starting RePORTaLiN MCP Server",
        host=args.host or settings.mcp_host,
        port=args.port or settings.mcp_port,
        environment=settings.environment.value,
    )
    
    try:
        # Import and run the server
        from server.main import run_server
        
        run_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
        
    except Exception as e:
        logger.error("Server failed to start", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
