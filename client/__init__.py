"""
RePORTaLiN MCP Client Adapter Package.

This package provides a universal client adapter for connecting to
MCP servers and translating tool schemas for different LLM providers.

Components:
    - UniversalMCPClient: Main client class for MCP server communication
    - MCPAgent: Agent driver implementing ReAct loop (LLM + Tools)
    - AgentConfig: Configuration dataclass for agent settings
    - Exception classes for error handling
    - create_client: Convenience function for quick client creation

The UniversalMCPClient class (aliased as universal_client) handles:
    - SSE connection lifecycle with AsyncExitStack
    - Bearer token authentication
    - Schema adaptation for OpenAI and Anthropic APIs
    - Tool execution with flattened text output

The MCPAgent class handles:
    - ReAct (Reasoning + Action) loop implementation
    - Multi-turn conversation management
    - Support for OpenAI API and local LLMs (Ollama)
    - Automatic tool execution and result handling

Usage:
    >>> from client import UniversalMCPClient
    >>> # Or use the canonical Phase 3 import:
    >>> from client.universal_client import UniversalMCPClient
    >>> 
    >>> # Direct MCP client usage
    >>> async with UniversalMCPClient(
    ...     server_url="http://localhost:8000/mcp/sse",
    ...     auth_token="your-token"
    ... ) as client:
    ...     tools = await client.get_tools_for_openai()
    ...     result = await client.execute_tool("health_check", {})
    >>> 
    >>> # Agent usage (recommended for LLM integration)
    >>> from client import MCPAgent
    >>> async with await MCPAgent.create() as agent:
    ...     response = await agent.run("Check the system status")
    ...     print(response)
"""

# Primary imports from mcp_client (implementation)
from client.mcp_client import (
    UniversalMCPClient,
    MCPClientError,
    MCPConnectionError,
    MCPAuthenticationError,
    MCPToolExecutionError,
    MCPRetryConfig,
    OpenAITool,
    AnthropicTool,
    create_client,
)
from client.agent import (
    MCPAgent,
    AgentConfig,
    AgentError,
    AgentConfigError,
    AgentExecutionError,
    DEFAULT_SYSTEM_PROMPT,
    run_agent,
)

__all__ = [
    # Main client class
    "UniversalMCPClient",
    # Agent classes
    "MCPAgent",
    "AgentConfig",
    # Configuration
    "MCPRetryConfig",
    # Exception classes
    "MCPClientError",
    "MCPConnectionError",
    "MCPAuthenticationError",
    "MCPToolExecutionError",
    "AgentError",
    "AgentConfigError",
    "AgentExecutionError",
    # Type definitions
    "OpenAITool",
    "AnthropicTool",
    # Constants
    "DEFAULT_SYSTEM_PROMPT",
    # Convenience functions
    "create_client",
    "run_agent",
]
