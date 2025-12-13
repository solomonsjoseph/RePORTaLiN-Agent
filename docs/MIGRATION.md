# Migration Guide: Version 2.x to src-layout

This guide helps you migrate from the old flat project structure to the new src-layout architecture introduced in version 2.1.0+.

## What Changed?

The project has been restructured to follow Python packaging best practices (PEP 517/518/621) with **src-layout**. This provides better namespace isolation, prevents import conflicts, and enables proper editable installs.

### Directory Structure Changes

**Before (v2.0.x):**
```
RePORTaLiN-Agent/
├── server/          # MCP server
├── client/          # MCP client
├── shared/          # Shared utilities
├── scripts/         # Data processing
├── tests/           # Tests
├── Dockerfile       # Docker config
└── main.py          # CLI entry point
```

**After (v2.1.0+):**
```
RePORTaLiN-Agent/
├── src/
│   └── reportalin/              # Importable package
│       ├── server/              # MCP server
│       ├── client/              # MCP client
│       ├── core/                # Core utilities (consolidated)
│       ├── data/                # Data processing
│       ├── types/               # Type definitions
│       └── cli/                 # CLI commands
├── tests/                       # Tests (unchanged)
├── docker/                      # Docker configs (moved)
├── examples/                    # Examples (new)
└── pyproject.toml              # Project metadata
```

## Breaking Changes

### Import Path Changes

All imports must be updated to use the `reportalin` namespace:

| Old Import | New Import |
|------------|------------|
| `from server.config import Settings` | `from reportalin.server.config import Settings` |
| `from server.tools import ...` | `from reportalin.server.tools import ...` |
| `from client.mcp_client import UniversalMCPClient` | `from reportalin.client.mcp_client import UniversalMCPClient` |
| `from shared.constants import ...` | `from reportalin.core.constants import ...` |
| `from shared.types import ...` | `from reportalin.types.models import ...` |
| `from scripts.deidentify import ...` | `from reportalin.data.deidentify import ...` |

### Command Changes

**Starting the MCP Server:**

```bash
# Old
uv run python -m server
uv run uvicorn server.main:app

# New
uv run python -m reportalin.server
uv run uvicorn reportalin.server.main:app

# Or use the new entry point
reportalin-mcp --help
```

**Running CLI Commands:**

```bash
# Old
python main.py --help
python verify.py

# New
python -m reportalin.cli.pipeline --help
python -m reportalin.cli.verify

# Or use the new entry points
reportalin --help
reportalin-client --help
```

### Docker Changes

Docker files have been moved to the `docker/` directory:

```bash
# Old
docker build -f Dockerfile -t reportalin-mcp:latest .

# New
docker build -f docker/Dockerfile -t reportalin-mcp:latest .
```

Docker Compose configurations have been updated automatically - no changes required if you're using `docker-compose.yml`.

### Claude Desktop Configuration

Update your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "reportalin": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/absolute/path/to/RePORTaLiN-Agent",
        "python", "-m", "reportalin.server",
        "--transport", "stdio"
      ],
      "env": {
        "MCP_AUTH_TOKEN": "your-token-here"
      }
    }
  }
}
```

**Changed:** `"python", "-m", "server"` → `"python", "-m", "reportalin.server"`

### CI/CD Changes

If you have custom CI/CD pipelines, update paths:

**GitHub Actions:**
```yaml
# Old
- run: pytest tests/ --cov=server --cov=client

# New
- run: pytest tests/ --cov=src/reportalin
```

**Code Quality Tools:**
```bash
# Old
mypy server client

# New
mypy src/reportalin
```

## Migration Steps

### For Users (Running the Server)

1. **Pull the latest code:**
   ```bash
   git pull origin main
   ```

2. **Reinstall dependencies:**
   ```bash
   uv sync --all-extras
   ```

3. **Update your Claude Desktop config** (if using):
   - Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Change `"python", "-m", "server"` to `"python", "-m", "reportalin.server"`
   - Restart Claude Desktop

4. **Update any scripts** that start the server:
   - Change `uv run python -m server` to `uv run python -m reportalin.server`
   - Or use the new entry point: `reportalin-mcp`

5. **Test your setup:**
   ```bash
   # Test server starts
   reportalin-mcp --help

   # Test in stdio mode
   MCP_TRANSPORT=stdio reportalin-mcp

   # Test HTTP mode
   uv run uvicorn reportalin.server.main:app --host 127.0.0.1 --port 8000
   curl http://localhost:8000/health
   ```

### For Developers (Building on the Project)

1. **Update your development environment:**
   ```bash
   git pull origin main
   uv sync --all-extras
   ```

2. **Update your imports:**
   - Run a find-and-replace in your custom code:
     - `from server.` → `from reportalin.server.`
     - `from client.` → `from reportalin.client.`
     - `from shared.` → `from reportalin.core.`
     - `import server.` → `import reportalin.server.`
     - `import client.` → `import reportalin.client.`

3. **Update test imports** (if you have custom tests):
   ```python
   # Old
   from server.tools import combined_search
   from client.mcp_client import UniversalMCPClient

   # New
   from reportalin.server.tools import combined_search
   from reportalin.client.mcp_client import UniversalMCPClient
   ```

4. **Run tests to verify:**
   ```bash
   uv run pytest tests/
   ```

5. **Update Docker builds** (if you have custom Dockerfiles):
   - Reference `docker/Dockerfile` for build configuration
   - Ensure COPY commands reference the correct paths

## Backward Compatibility

**Shim modules** have been added for gradual migration:

- `server/config.py` → Re-exports from `reportalin.server.config`
- `server/logger.py` → Re-exports from `reportalin.core.logging`
- `server/auth.py` → Re-exports from `reportalin.server.auth`
- `shared/constants.py` → Re-exports from `reportalin.core.constants`

**These shims will be removed in version 3.0.0.** Please update your imports now.

## Benefits of the New Structure

1. **Namespace Isolation**: No import conflicts with other packages
2. **Proper Packaging**: Install with `pip install -e .` for development
3. **Type Safety**: Full type hints with mypy strict mode
4. **Better IDE Support**: Clearer package boundaries and imports
5. **Standards Compliant**: Follows PEP 517/518/621
6. **Cleaner Repository**: Organized structure with `docker/`, `examples/`, `tests/`

## Troubleshooting

### ImportError: No module named 'server'

**Problem:** Old import paths in your custom code.

**Solution:** Update imports to use `reportalin.server` namespace:
```python
from reportalin.server.config import get_settings
```

### ModuleNotFoundError: No module named 'reportalin'

**Problem:** Package not installed or virtual environment not activated.

**Solution:**
```bash
# Reinstall the package in editable mode
uv pip install -e .

# Or resync dependencies
uv sync
```

### Docker build fails: COPY failed

**Problem:** Docker COPY commands reference old paths.

**Solution:** Update Dockerfile COPY paths to use `src/reportalin/` and `docker/` directories.

### Tests failing after migration

**Problem:** Test files using old import paths.

**Solution:** Update test imports:
```bash
# Find all test files with old imports
grep -r "from server\." tests/
grep -r "from client\." tests/
grep -r "from shared\." tests/

# Update them to use reportalin.* namespace
```

## Getting Help

If you encounter issues during migration:

1. Check the [README.md](README.md) for updated documentation
2. Review the [CHANGELOG.md](CHANGELOG.md) for detailed changes
3. Open an issue on GitHub with your error message and configuration

## Example: Complete Migration Workflow

Here's a complete example for a typical user:

```bash
# 1. Pull latest code
git pull origin main

# 2. Clean old virtual environment (optional but recommended)
rm -rf .venv

# 3. Reinstall with uv
uv sync --all-extras

# 4. Update Claude Desktop config
# Edit ~/Library/Application Support/Claude/claude_desktop_config.json
# Change: "python", "-m", "server"
# To: "python", "-m", "reportalin.server"

# 5. Restart Claude Desktop
# Quit and reopen Claude Desktop app

# 6. Test the server
reportalin-mcp --help

# 7. Start the server
MCP_TRANSPORT=stdio MCP_AUTH_TOKEN=your-token reportalin-mcp

# Done! Your migration is complete.
```

## Summary

The migration to src-layout is a one-time change that provides long-term benefits for maintainability, type safety, and standards compliance. The main change is adding `reportalin.` prefix to all imports.

**Key takeaway:** Change `from server.*` to `from reportalin.server.*` everywhere in your code.
