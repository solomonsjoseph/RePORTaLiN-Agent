<div align="center">

# RePORTaLiN MCP Server

**Production-ready Model Context Protocol (MCP) server for privacy-preserving clinical data access**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP 1.0+](https://img.shields.io/badge/MCP-1.0+-green.svg)](https://modelcontextprotocol.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![uv](https://img.shields.io/badge/uv-package%20manager-blueviolet.svg)](https://docs.astral.sh/uv/)

[Quick Start](#quick-start) • [Architecture](#architecture) • [Configuration](#configuration) • [Tools](#available-tools) • [Client Integration](#client-integration) • [Docker](#docker-deployment)

</div>

---

## Overview

RePORTaLiN MCP Server is a **Model Context Protocol** implementation that enables LLM-powered applications to securely query clinical research data. Built with privacy-by-design principles, it enforces k-anonymity thresholds and provides audit logging for HIPAA/DPDPA compliance.

### Key Features

- 🔒 **Privacy-Preserving** — K-anonymity enforcement (k≥5) on all aggregate queries
- 🌐 **Universal Transport** — Supports both stdio (Claude Desktop) and HTTP/SSE protocols
- 🔐 **Secure by Default** — Bearer token authentication with constant-time comparison
- 📊 **Schema-Aware Tools** — Pydantic-validated inputs with JSON Schema for LLM reliability
- 🐳 **Production-Ready** — Multi-stage Docker builds with non-root user and health checks

---

## Quick Start

### Prerequisites

- Python 3.10+ (3.11 or 3.13 recommended)
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip

### Local Development (with uv)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/your-org/RePORTaLiN-Agent.git
cd RePORTaLiN-Agent

# Install dependencies (uv creates .venv automatically)
uv sync --all-extras

# Configure environment
cp .env.example .env
# Edit .env with your MCP_AUTH_TOKEN

# Start the MCP server (HTTP/SSE mode)
uv run uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload

# Or start in stdio mode (for Claude Desktop)
MCP_TRANSPORT=stdio uv run python -m server
```

### Production Deployment (with Docker)

```bash
# Clone and configure
git clone https://github.com/your-org/RePORTaLiN-Agent.git
cd RePORTaLiN-Agent
cp .env.example .env

# Generate a secure auth token
echo "MCP_AUTH_TOKEN=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env

# Build and run with Docker Compose
docker compose up --build mcp-server

# Server is now available at http://localhost:8000
# API docs at http://localhost:8000/docs (local environment only)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LLM Application                                │
│                    (Claude Desktop / Custom Agent)                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   UniversalMCPClient      │
                    │   (client/mcp_client.py)  │
                    │   - Schema Adapters       │
                    │   - OpenAI/Anthropic      │
                    └─────────────┬─────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
    ┌─────────▼─────────┐                 ┌───────────▼───────────┐
    │   stdio Transport │                 │   HTTP/SSE Transport  │
    │   (Claude Desktop)│                 │   (FastAPI + uvicorn) │
    └─────────┬─────────┘                 └───────────┬───────────┘
              │                                       │
              └───────────────────┬───────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     MCPAuthMiddleware     │
                    │   (Bearer Token Auth)     │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      FastMCP Server       │
                    │   (server/tools.py)       │
                    │   - Tool Registration     │
                    │   - Input Validation      │
                    │   - K-Anonymity Checks    │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     Clinical Data Layer   │
                    │   - Data Dictionary       │
                    │   - Aggregate Statistics  │
                    │   - Encrypted Audit Logs  │
                    └───────────────────────────┘
```

### SSE Handshake Flow

1. **Client** → `GET /mcp/sse` with `Authorization: Bearer <token>`
2. **Server** → Validates token, establishes SSE stream
3. **Server** → Sends `endpoint` event: `/mcp/messages?session_id=<uuid>`
4. **Client** → `POST /mcp/messages` with JSON-RPC 2.0 requests
5. **Server** → Streams responses via SSE `message` events

---

## Configuration

All configuration is managed via environment variables. Create a `.env` file from `.env.example`:

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `local` | Deployment environment: `local`, `development`, `staging`, `production` |
| `MCP_HOST` | No | `127.0.0.1` | Server bind address |
| `MCP_PORT` | No | `8000` | Server port |
| `MCP_AUTH_TOKEN` | **Yes*** | — | Bearer token for API authentication |
| `MCP_AUTH_ENABLED` | No | `true` | Enable/disable authentication |
| `LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | No | `auto` | Log format: `auto`, `json`, `pretty` |
| `PRIVACY_MODE` | No | `strict` | Privacy enforcement: `strict`, `standard` |
| `MIN_K_ANONYMITY` | No | `5` | Minimum k-anonymity threshold |
| `OPENAI_API_KEY` | No | — | OpenAI API key (for agent features) |
| `ANTHROPIC_API_KEY` | No | — | Anthropic API key (for agent features) |
| `LLM_API_KEY` | No | — | Generic LLM API key (agent) |
| `LLM_BASE_URL` | No | — | Custom LLM endpoint (Ollama, vLLM, etc.) |

> **\*** `MCP_AUTH_TOKEN` is required in `staging` and `production` environments. In `local`/`development`, a dev token is auto-generated if not provided.

### Generate a Secure Token

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Available Tools

The MCP server exposes privacy-safe tools that LLMs can invoke:

### `query_database`

Execute validated SQL-like queries against clinical data.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | SQL SELECT query (10-2000 chars) |
| `limit` | integer | No | Max rows to return (1-1000, default: 100) |
| `include_metadata` | boolean | No | Include column metadata (default: false) |

**Example:**
```json
{
  "name": "query_database",
  "arguments": {
    "query": "SELECT age_group, COUNT(*) FROM patients GROUP BY age_group",
    "limit": 50
  }
}
```

### `search_dictionary`

Search the data dictionary for variable definitions.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search_term` | string | Yes | Term to search for |
| `category` | string | No | Filter by category |
| `limit` | integer | No | Max results (default: 20) |

### `fetch_metrics`

Retrieve aggregate statistics with k-anonymity protection.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `metric_type` | enum | Yes | `count`, `sum`, `average`, `min`, `max`, `distribution` |
| `field` | string | Yes | Field to aggregate |
| `filters` | object | No | Filter conditions |

### `health_check`

Server health status and capabilities.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `include_capabilities` | boolean | No | Include tool listing (default: false) |

---

## Client Integration

### Using UniversalMCPClient

The `UniversalMCPClient` provides a Python interface for connecting to the MCP server with automatic schema adaptation for different LLM providers.

```python
import asyncio
from client.mcp_client import UniversalMCPClient

async def main():
    # Connect to MCP server
    async with UniversalMCPClient(
        server_url="http://localhost:8000/mcp/sse",
        auth_token="your-secure-token-here"
    ) as client:
        
        # Get tools formatted for OpenAI
        openai_tools = await client.get_tools_for_openai()
        print(f"Available tools: {[t['function']['name'] for t in openai_tools]}")
        
        # Get tools formatted for Anthropic Claude
        anthropic_tools = await client.get_tools_for_anthropic()
        
        # Execute a tool
        result = await client.execute_tool(
            "query_database",
            {"query": "SELECT COUNT(*) FROM studies", "limit": 10}
        )
        print(f"Result: {result}")
        
        # Health check
        health = await client.execute_tool("health_check", {})
        print(f"Server status: {health}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Using with OpenAI Function Calling

```python
from openai import OpenAI
from client.mcp_client import UniversalMCPClient

async def agent_loop():
    client = OpenAI()
    
    async with UniversalMCPClient(
        "http://localhost:8000/mcp/sse", 
        "your-token"
    ) as mcp:
        # Get tools in OpenAI format
        tools = await mcp.get_tools_for_openai()
        
        messages = [{"role": "user", "content": "What studies are available?"}]
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=tools
        )
        
        # Handle tool calls
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                result = await mcp.execute_tool(
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments)
                )
                # Process result...
```

### Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "reportalin": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/absolute/path/to/RePORTaLiN-Agent",
        "python", "-m", "server",
        "--transport", "stdio"
      ],
      "env": {
        "MCP_AUTH_TOKEN": "your-secure-token",
        "PRIVACY_MODE": "strict"
      }
    }
  }
}
```

---

## Docker Deployment

### Build Options

```bash
# Production build (uv-based, recommended)
DOCKER_BUILDKIT=1 docker build -f Dockerfile.uv -t reportalin-mcp:latest .

# Legacy build (pip-based)
DOCKER_BUILDKIT=1 docker build -t reportalin-mcp:legacy .

# Secure build with additional hardening
DOCKER_BUILDKIT=1 docker build -f Dockerfile.secure -t reportalin-mcp:secure .
```

### Run with Docker Compose

```bash
# Production mode
docker compose up mcp-server

# Development mode (with hot reload)
docker compose up mcp-server-dev

# Rebuild and start
docker compose up --build mcp-server

# Run in background
docker compose up -d mcp-server

# View logs
docker compose logs -f mcp-server

# Stop
docker compose down
```

### Run Standalone

```bash
docker run -d \
  --name reportalin-mcp \
  -p 8000:8000 \
  -e MCP_AUTH_TOKEN=your-secure-token \
  -e ENVIRONMENT=production \
  -v $(pwd)/results:/app/results:ro \
  -v $(pwd)/encrypted_logs:/app/encrypted_logs \
  reportalin-mcp:latest
```

### Health Checks

```bash
# Check container health status
docker inspect --format='{{.State.Health.Status}}' reportalin-mcp

# Manual health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/ready
```

### Docker Features Summary

| Feature | Implementation |
|---------|----------------|
| Base Image | `python:3.11-slim` |
| Package Manager | `uv` with `pyproject.toml` |
| Init System | `tini` for proper signal handling |
| User | Non-root `app` (UID 1000) |
| Build Strategy | Multi-stage for minimal size |
| Health Check | HTTP `/health` endpoint |
| Logging | JSON format with rotation |

---

## API Endpoints

### Public Endpoints (No Auth)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness probe |
| `/ready` | GET | Readiness probe |

### Protected Endpoints (Bearer Token)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Detailed server status |
| `/tools` | GET | List available tools |
| `/info` | GET | Server info and connection details |
| `/mcp/sse` | GET | SSE stream for MCP protocol |
| `/mcp/messages` | POST | JSON-RPC message handler |

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs (local environment only)
- **ReDoc**: http://localhost:8000/redoc (local environment only)

---

## Security

### Authentication

- All MCP endpoints require Bearer token authentication
- Tokens are validated using constant-time comparison (timing-attack resistant)
- Failed auth attempts are logged with request metadata

### Privacy Protection

- K-anonymity enforcement (configurable threshold, default k=5)
- No raw patient data exposed—only aggregates and schemas
- Encrypted audit logging with RSA/AES hybrid encryption

### Container Security

- Non-root user execution
- Read-only volume mounts for data
- Resource limits via Docker Compose
- No new privileges security option

---

## Troubleshooting

### Connection Refused

```bash
# Check if server is running
curl http://localhost:8000/health

# Check Docker logs
docker compose logs mcp-server
```

### Authentication Failed

```bash
# Verify token is set
echo $MCP_AUTH_TOKEN

# Test with curl
curl -H "Authorization: Bearer $MCP_AUTH_TOKEN" http://localhost:8000/tools
```

### SSE Connection Drops

- Increase `sse_read_timeout` in client configuration
- Check for proxy/load balancer SSE support
- Verify network allows long-lived connections

---

## Development

### Running Tests

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# With coverage
uv run pytest --cov=server --cov=client
```

### Code Quality

```bash
# Format code
uv run black .

# Lint
uv run ruff check .

# Type check
uv run mypy server client
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ by the RePORTaLiN Team**

[Report Bug](https://github.com/your-org/RePORTaLiN-Agent/issues) • [Request Feature](https://github.com/your-org/RePORTaLiN-Agent/issues)

</div>
