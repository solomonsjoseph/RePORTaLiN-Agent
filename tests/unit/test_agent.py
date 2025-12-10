"""
Tests for the MCP Agent Driver.

This module tests the agent logic including:
- Configuration loading
- Connection lifecycle
- ReAct loop execution
- Tool call handling
- Error handling

Note: These tests use mocks to avoid requiring a running server or LLM.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import Function

from client.agent import (
    AgentConfig,
    AgentConfigError,
    AgentError,
    AgentExecutionError,
    MCPAgent,
)

# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_config() -> AgentConfig:
    """Create a sample agent configuration."""
    return AgentConfig(
        llm_api_key="test-api-key",
        llm_base_url=None,
        llm_model="gpt-4o-mini",
        mcp_server_url="http://localhost:8000/mcp/sse",
        mcp_auth_token="test-token",
        max_iterations=5,
        temperature=0.7,
    )


@pytest.fixture
def local_llm_config() -> AgentConfig:
    """Create configuration for local LLM (Ollama)."""
    return AgentConfig(
        llm_api_key="",  # Not needed for local
        llm_base_url="http://localhost:11434/v1",
        llm_model="llama3.2",
        mcp_server_url="http://localhost:8000/mcp/sse",
        mcp_auth_token="test-token",
    )


@pytest.fixture
def mock_mcp_client() -> AsyncMock:
    """Create a mock MCP client.
    
    Note: combined_search is the DEFAULT tool for all queries.
    """
    client = AsyncMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.get_tools_for_openai = AsyncMock(return_value=[
        {
            "type": "function",
            "function": {
                "name": "combined_search",
                "description": "DEFAULT - Search ALL data sources for statistics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept": {"type": "string"},
                    },
                    "required": ["concept"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_data_dictionary",
                "description": "Variable definitions ONLY (no statistics)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        },
    ])
    client.execute_tool = AsyncMock(return_value='{"concept": "diabetes", "variables_found": 5}')
    return client


@pytest.fixture
def mock_llm_client() -> AsyncMock:
    """Create a mock OpenAI client."""
    client = AsyncMock()
    client.close = AsyncMock()
    return client


def create_completion_response(
    content: str | None = "This is a test response",
    tool_calls: list[dict] | None = None,
) -> ChatCompletion:
    """Create a mock ChatCompletion response."""
    message_tool_calls = None
    if tool_calls:
        message_tool_calls = [
            ChatCompletionMessageToolCall(
                id=tc["id"],
                type="function",
                function=Function(
                    name=tc["name"],
                    arguments=json.dumps(tc.get("arguments", {})),
                ),
            )
            for tc in tool_calls
        ]

    message = ChatCompletionMessage(
        role="assistant",
        content=content,
        tool_calls=message_tool_calls,
    )

    choice = Choice(
        index=0,
        message=message,
        finish_reason="stop" if not tool_calls else "tool_calls",
    )

    return ChatCompletion(
        id="test-completion-id",
        choices=[choice],
        created=int(datetime.now(timezone.utc).timestamp()),
        model="gpt-4o-mini",
        object="chat.completion",
    )


# =============================================================================
# Configuration Tests
# =============================================================================

class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_config_creation(self, sample_config: AgentConfig) -> None:
        """Test config can be created with required arguments."""
        assert sample_config.llm_api_key == "test-api-key"
        assert sample_config.llm_model == "gpt-4o-mini"
        assert sample_config.mcp_server_url == "http://localhost:8000/mcp/sse"
        assert sample_config.is_local_llm is False
        assert sample_config.provider_name == "OpenAI"

    def test_local_llm_config(self, local_llm_config: AgentConfig) -> None:
        """Test configuration for local LLM."""
        assert local_llm_config.is_local_llm is True
        assert local_llm_config.provider_name == "Ollama"
        assert local_llm_config.llm_base_url == "http://localhost:11434/v1"

    def test_config_from_env_missing_api_key(self) -> None:
        """Test config loading fails without API key or base URL."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AgentConfigError) as exc_info:
                AgentConfig.from_env()
            assert "LLM_API_KEY" in str(exc_info.value)

    def test_config_from_env_with_api_key(self) -> None:
        """Test config loading with API key."""
        env = {
            "LLM_API_KEY": "test-key",
            "MCP_AUTH_TOKEN": "test-token",
            "LLM_MODEL": "gpt-4",
        }
        with patch.dict("os.environ", env, clear=True):
            config = AgentConfig.from_env()
            assert config.llm_api_key == "test-key"
            assert config.llm_model == "gpt-4"

    def test_config_from_env_with_openai_api_key(self) -> None:
        """Test config loading with OPENAI_API_KEY fallback."""
        env = {
            "OPENAI_API_KEY": "openai-key",
            "MCP_AUTH_TOKEN": "test-token",
        }
        with patch.dict("os.environ", env, clear=True):
            config = AgentConfig.from_env()
            assert config.llm_api_key == "openai-key"

    def test_config_from_env_with_local_llm(self) -> None:
        """Test config loading for local LLM (no API key required)."""
        env = {
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "MCP_AUTH_TOKEN": "test-token",
        }
        with patch.dict("os.environ", env, clear=True):
            config = AgentConfig.from_env()
            assert config.llm_base_url == "http://localhost:11434/v1"
            assert config.is_local_llm is True

    def test_provider_name_variations(self) -> None:
        """Test provider name detection for various base URLs."""
        # Ollama
        config = AgentConfig(
            llm_api_key="test",
            llm_base_url="http://localhost:11434/v1",
        )
        assert config.provider_name == "Ollama"

        # Generic localhost
        config = AgentConfig(
            llm_api_key="test",
            llm_base_url="http://localhost:1234/v1",
        )
        assert config.provider_name == "Local LLM"

        # Custom remote
        config = AgentConfig(
            llm_api_key="test",
            llm_base_url="http://my-llm-server.com/v1",
        )
        assert config.provider_name == "Custom API"


# =============================================================================
# Agent Initialization Tests
# =============================================================================

class TestAgentInitialization:
    """Tests for MCPAgent initialization."""

    def test_agent_creation(self, sample_config: AgentConfig) -> None:
        """Test agent can be created with config."""
        agent = MCPAgent(sample_config)
        assert agent.config == sample_config
        assert agent._connected is False
        assert agent.messages == []

    @pytest.mark.asyncio
    async def test_agent_connect(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test agent connection establishes MCP and loads tools."""
        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        await agent.connect()

        assert agent._connected is True
        mock_mcp_client.connect.assert_called_once()
        mock_mcp_client.get_tools_for_openai.assert_called_once()
        assert len(agent._tools) == 2
        assert agent._tool_names == ["combined_search", "search_data_dictionary"]

        # Check system prompt was added
        assert len(agent.messages) == 1
        assert agent.messages[0]["role"] == "system"

        await agent.close()

    @pytest.mark.asyncio
    async def test_agent_context_manager(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test agent works as async context manager."""
        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            assert agent._connected is True

        mock_mcp_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_close_cleans_up(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test agent close properly cleans up resources."""
        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        await agent.connect()
        await agent.close()

        assert agent._connected is False
        mock_mcp_client.close.assert_called_once()
        mock_llm_client.close.assert_called_once()


# =============================================================================
# ReAct Loop Tests
# =============================================================================

class TestReActLoop:
    """Tests for the ReAct loop implementation."""

    @pytest.mark.asyncio
    async def test_run_simple_response(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test simple response without tool calls."""
        # Setup LLM to return direct response
        mock_llm_client.chat.completions.create = AsyncMock(
            return_value=create_completion_response("The system is healthy!")
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            response = await agent.run("Check the status")

        assert response == "The system is healthy!"
        assert len(agent.messages) == 3  # system + user + assistant

    @pytest.mark.asyncio
    async def test_run_with_tool_call(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test response with single tool call."""
        # First call returns tool call, second returns final response
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=[
                create_completion_response(
                    content=None,
                    tool_calls=[{
                        "id": "call_123",
                        "name": "combined_search",
                        "arguments": {"concept": "diabetes"},
                    }],
                ),
                create_completion_response("Found 5 diabetes-related variables in the dataset."),
            ]
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            response = await agent.run("What diabetes data is available?")

        assert "diabetes" in response.lower() or "variables" in response.lower()
        mock_mcp_client.execute_tool.assert_called_once_with("combined_search", {"concept": "diabetes"})

    @pytest.mark.asyncio
    async def test_run_with_multiple_tool_calls(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test response with multiple tool calls in one response."""
        # LLM requests two tools at once
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=[
                create_completion_response(
                    content=None,
                    tool_calls=[
                        {
                            "id": "call_1",
                            "name": "combined_search",
                            "arguments": {"concept": "diabetes"},
                        },
                        {
                            "id": "call_2",
                            "name": "search_data_dictionary",
                            "arguments": {"query": "HIV"},
                        },
                    ],
                ),
                create_completion_response("Found diabetes and HIV-related variables."),
            ]
        )

        mock_mcp_client.execute_tool = AsyncMock(
            side_effect=['{"concept": "diabetes", "variables_found": 5}', '{"query": "HIV", "variables_found": 3}']
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            await agent.run("Find diabetes and HIV variables")

        assert mock_mcp_client.execute_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_run_max_iterations_exceeded(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test that max iterations prevents infinite loops."""
        # LLM always returns tool calls (infinite loop scenario)
        mock_llm_client.chat.completions.create = AsyncMock(
            return_value=create_completion_response(
                content=None,
                tool_calls=[{
                    "id": "call_loop",
                    "name": "combined_search",
                    "arguments": {"concept": "test"},
                }],
            )
        )

        config = AgentConfig(
            llm_api_key="test",
            max_iterations=3,  # Low limit for testing
        )

        agent = MCPAgent(
            config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            with pytest.raises(AgentExecutionError) as exc_info:
                await agent.run("Do something")

        assert "maximum iterations" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_not_connected_raises_error(
        self,
        sample_config: AgentConfig,
    ) -> None:
        """Test that run() raises error if not connected."""
        agent = MCPAgent(sample_config)

        with pytest.raises(AgentError) as exc_info:
            await agent.run("Test prompt")

        assert "not connected" in str(exc_info.value).lower()


# =============================================================================
# Message History Tests
# =============================================================================

class TestMessageHistory:
    """Tests for conversation history management."""

    @pytest.mark.asyncio
    async def test_message_history_maintained(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test that message history is properly maintained."""
        mock_llm_client.chat.completions.create = AsyncMock(
            return_value=create_completion_response("Response 1")
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            await agent.run("First prompt")

            # History should have: system + user + assistant
            assert len(agent.messages) == 3
            assert agent.messages[0]["role"] == "system"
            assert agent.messages[1]["role"] == "user"
            assert agent.messages[2]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_tool_results_in_history(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test that tool results are added to history correctly."""
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=[
                create_completion_response(
                    content=None,
                    tool_calls=[{
                        "id": "call_abc",
                        "name": "combined_search",
                        "arguments": {"concept": "diabetes"},
                    }],
                ),
                create_completion_response("Done!"),
            ]
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            await agent.run("Find diabetes data")

            # Find tool result message
            tool_messages = [m for m in agent.messages if m.get("role") == "tool"]
            assert len(tool_messages) == 1
            assert tool_messages[0]["tool_call_id"] == "call_abc"

    @pytest.mark.asyncio
    async def test_reset_conversation(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test conversation reset."""
        mock_llm_client.chat.completions.create = AsyncMock(
            return_value=create_completion_response("Response")
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            await agent.run("Test")
            assert len(agent.messages) == 3

            agent.reset_conversation()

            # Should only have system prompt
            assert len(agent.messages) == 1
            assert agent.messages[0]["role"] == "system"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_tool_execution_error_handled(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test that tool execution errors are handled gracefully."""
        from client.mcp_client import MCPToolExecutionError

        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=[
                create_completion_response(
                    content=None,
                    tool_calls=[{
                        "id": "call_fail",
                        "name": "combined_search",
                        "arguments": {"concept": "nonexistent"},
                    }],
                ),
                create_completion_response("The search failed."),
            ]
        )

        # Make tool execution fail
        mock_mcp_client.execute_tool = AsyncMock(
            side_effect=MCPToolExecutionError(
                "Search failed",
                tool_name="combined_search",
            )
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            # Should not raise - error is captured and sent to LLM
            response = await agent.run("Search for nonexistent data")
            assert response is not None

    @pytest.mark.asyncio
    async def test_llm_error_raises_execution_error(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test that LLM errors are propagated."""
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            with pytest.raises(AgentExecutionError) as exc_info:
                await agent.run("Test")

        assert "rate limit" in str(exc_info.value).lower()


# =============================================================================
# Integration Tests (with mocked externals)
# =============================================================================

class TestIntegration:
    """Integration tests with full agent flow."""

    @pytest.mark.asyncio
    async def test_full_react_loop(
        self,
        sample_config: AgentConfig,
        mock_mcp_client: AsyncMock,
        mock_llm_client: AsyncMock,
    ) -> None:
        """Test complete ReAct loop with tool calls and final response."""
        # Simulate a realistic conversation
        mock_llm_client.chat.completions.create = AsyncMock(
            side_effect=[
                # First: Search for diabetes data
                create_completion_response(
                    content="Let me search for diabetes-related data first.",
                    tool_calls=[{
                        "id": "call_search",
                        "name": "combined_search",
                        "arguments": {"concept": "diabetes"},
                    }],
                ),
                # Second: Look up specific variable definitions
                create_completion_response(
                    content="Found diabetes variables. Now let me get the definitions.",
                    tool_calls=[{
                        "id": "call_dict",
                        "name": "search_data_dictionary",
                        "arguments": {"query": "DMSTAT"},
                    }],
                ),
                # Final: Summarize results
                create_completion_response(
                    "Found 5 diabetes-related variables including DMSTAT for diabetes status."
                ),
            ]
        )

        mock_mcp_client.execute_tool = AsyncMock(
            side_effect=[
                '{"concept": "diabetes", "variables_found": 5, "statistics": {"total": 100}}',
                '{"query": "DMSTAT", "variables_found": 1, "variables": [{"field_name": "DMSTAT"}]}',
            ]
        )

        agent = MCPAgent(
            sample_config,
            mcp_client=mock_mcp_client,
            llm_client=mock_llm_client,
        )

        async with agent:
            response = await agent.run(
                "Check the system status and then query the users table"
            )

        assert "healthy" in response.lower()
        assert "users" in response.lower()
        assert mock_mcp_client.execute_tool.call_count == 2
