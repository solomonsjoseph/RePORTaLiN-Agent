"""
Tests for the CLI entry point module.

This module tests the command line interface for the MCP server,
including argument parsing and version display.

Tests cover:
- Argument parsing
- Version flag handling
- Default values
"""

import sys
from unittest.mock import patch

import pytest

from server.__main__ import main, parse_args

# =============================================================================
# Argument Parsing Tests
# =============================================================================


class TestParseArgs:
    """Tests for the parse_args function."""

    def test_default_args(self) -> None:
        """Test that default arguments are None."""
        with patch.object(sys, "argv", ["server"]):
            args = parse_args()
            assert args.host is None
            assert args.port is None
            assert args.reload is False
            assert args.version is False

    def test_host_argument(self) -> None:
        """Test parsing --host argument."""
        with patch.object(sys, "argv", ["server", "--host", "0.0.0.0"]):
            args = parse_args()
            assert args.host == "0.0.0.0"

    def test_port_argument(self) -> None:
        """Test parsing --port argument."""
        with patch.object(sys, "argv", ["server", "--port", "9000"]):
            args = parse_args()
            assert args.port == 9000

    def test_reload_flag(self) -> None:
        """Test parsing --reload flag."""
        with patch.object(sys, "argv", ["server", "--reload"]):
            args = parse_args()
            assert args.reload is True

    def test_version_flag(self) -> None:
        """Test parsing --version flag."""
        with patch.object(sys, "argv", ["server", "--version"]):
            args = parse_args()
            assert args.version is True

    def test_combined_arguments(self) -> None:
        """Test parsing multiple arguments together."""
        with patch.object(
            sys, "argv", ["server", "--host", "localhost", "--port", "8080", "--reload"]
        ):
            args = parse_args()
            assert args.host == "localhost"
            assert args.port == 8080
            assert args.reload is True


# =============================================================================
# Main Function Tests
# =============================================================================


class TestMain:
    """Tests for the main entry point function."""

    def test_version_flag_prints_and_exits(self, capsys: pytest.CaptureFixture) -> None:
        """Test that --version prints version info to stderr and returns 0.

        Note: Version output goes to stderr to avoid corrupting stdio JSON-RPC stream.
        """
        with patch.object(sys, "argv", ["server", "--version"]):
            result = main()

            assert result == 0
            captured = capsys.readouterr()
            # Version output goes to stderr to not corrupt stdio transport
            assert "reportalin-mcp" in captured.err.lower()
            assert "MCP Protocol" in captured.err

    def test_version_includes_protocol_version(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Test that --version includes the MCP protocol version."""
        with patch.object(sys, "argv", ["server", "--version"]):
            main()

            captured = capsys.readouterr()
            # Version output goes to stderr, should mention MCP Protocol version
            assert "2.0" in captured.err or "Protocol" in captured.err
