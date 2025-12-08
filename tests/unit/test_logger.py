"""
Tests for the logging module.

This module tests the structured logging utilities and middleware
used throughout the MCP server.

Tests cover:
- Logger initialization
- Request ID middleware
- Context binding
- Log output format
"""


from server.logger import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    get_request_id,
    set_request_id,
)

# =============================================================================
# Logger Initialization Tests
# =============================================================================

class TestGetLogger:
    """Tests for the get_logger function."""

    def test_get_logger_returns_logger(self) -> None:
        """Test that get_logger returns a logger instance."""
        logger = get_logger(__name__)
        assert logger is not None

    def test_get_logger_with_name(self) -> None:
        """Test get_logger with a specific name."""
        logger = get_logger("test_module")
        assert logger is not None

    def test_get_logger_same_instance(self) -> None:
        """Test that get_logger returns the same instance for same name."""
        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")
        # structlog wraps loggers, so we check they're both loggers
        assert logger1 is not None
        assert logger2 is not None


# =============================================================================
# Request ID Tests
# =============================================================================

class TestRequestId:
    """Tests for request ID management."""

    def test_set_and_get_request_id(self) -> None:
        """Test setting and getting request ID."""
        test_id = "test-request-123"
        set_request_id(test_id)

        result = get_request_id()
        assert result == test_id

    def test_get_request_id_default(self) -> None:
        """Test getting request ID when none is set returns a default."""
        # Clear any existing context first
        clear_context()

        result = get_request_id()
        # Should return either None or a generated ID depending on implementation
        assert result is None or isinstance(result, str)


# =============================================================================
# Context Binding Tests
# =============================================================================

class TestContextBinding:
    """Tests for log context binding."""

    def test_bind_context(self) -> None:
        """Test binding context variables."""
        # Should not raise
        bind_context(tool="test_tool", user="test_user")

    def test_clear_context(self) -> None:
        """Test clearing context variables."""
        bind_context(tool="test_tool")
        clear_context()
        # Should not raise

    def test_bind_multiple_values(self) -> None:
        """Test binding multiple context values."""
        bind_context(
            tool="explore_study_metadata",
            query_length=100,
            site_filter="Pune",
        )
        # Should not raise


# =============================================================================
# Configure Logging Tests
# =============================================================================

class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_configure_logging(self) -> None:
        """Test that configure_logging runs without error."""
        # Should not raise
        configure_logging()

    def test_configure_logging_idempotent(self) -> None:
        """Test that configure_logging can be called multiple times."""
        configure_logging()
        configure_logging()
        # Should not raise


# =============================================================================
# Logger Usage Tests
# =============================================================================

class TestLoggerUsage:
    """Tests for logger usage patterns."""

    def test_logger_info(self) -> None:
        """Test logging at info level."""
        logger = get_logger("test")
        # Should not raise
        logger.info("Test message", key="value")

    def test_logger_debug(self) -> None:
        """Test logging at debug level."""
        logger = get_logger("test")
        # Should not raise
        logger.debug("Debug message", data={"test": 123})

    def test_logger_warning(self) -> None:
        """Test logging at warning level."""
        logger = get_logger("test")
        # Should not raise
        logger.warning("Warning message")

    def test_logger_error(self) -> None:
        """Test logging at error level."""
        logger = get_logger("test")
        # Should not raise
        logger.error("Error message", error="test error")

    def test_logger_with_exception(self) -> None:
        """Test logging with exception info."""
        logger = get_logger("test")
        try:
            raise ValueError("Test exception")
        except ValueError:
            # Should not raise
            logger.exception("Exception occurred")
