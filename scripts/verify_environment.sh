#!/bin/bash
# =============================================================================
# RePORTaLiN Environment Verification Script
# =============================================================================
# Verifies all prerequisites for MCP clinical data server are installed
# Run: ./scripts/verify_environment.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=== RePORTaLiN MCP Environment Verification ==="
echo ""

# Track overall status
WARNINGS=0
ERRORS=0

# -----------------------------------------------------------------------------
# Check Python version
# -----------------------------------------------------------------------------
echo -n "Checking Python... "
if command -v python3 &> /dev/null; then
    python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    major=$(echo $python_version | cut -d. -f1)
    minor=$(echo $python_version | cut -d. -f2)
    
    if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
        echo -e "${GREEN}✓${NC} Python $python_version"
    else
        echo -e "${RED}✗${NC} Python $python_version (requires 3.10+)"
        ((ERRORS++))
    fi
else
    echo -e "${RED}✗${NC} Python not found"
    ((ERRORS++))
fi

# -----------------------------------------------------------------------------
# Check uv package manager
# -----------------------------------------------------------------------------
echo -n "Checking uv... "
if command -v uv &> /dev/null; then
    uv_version=$(uv --version 2>/dev/null | head -1)
    echo -e "${GREEN}✓${NC} $uv_version"
else
    echo -e "${RED}✗${NC} uv not found"
    echo "    Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    ((ERRORS++))
fi

# -----------------------------------------------------------------------------
# Check Docker (optional)
# -----------------------------------------------------------------------------
echo -n "Checking Docker... "
if command -v docker &> /dev/null; then
    docker_version=$(docker --version 2>/dev/null | head -1)
    echo -e "${GREEN}✓${NC} $docker_version"
else
    echo -e "${YELLOW}⚠${NC} Docker not found (optional, for sandboxed deployment)"
    ((WARNINGS++))
fi

# -----------------------------------------------------------------------------
# Check project dependencies
# -----------------------------------------------------------------------------
echo ""
echo "Checking Python dependencies..."

# Check if .venv exists
if [ -d ".venv" ]; then
    echo -e "  ${GREEN}✓${NC} Virtual environment found"
else
    echo -e "  ${YELLOW}⚠${NC} No .venv found. Run: uv sync --all-extras"
    ((WARNINGS++))
fi

# Try to import key packages
echo -n "  Checking MCP SDK... "
if uv run python -c "import mcp; print(mcp.__version__)" 2>/dev/null; then
    echo -e "    ${GREEN}✓${NC} MCP SDK installed"
else
    echo -e "    ${RED}✗${NC} MCP SDK not installed"
    ((ERRORS++))
fi

echo -n "  Checking FastAPI... "
if uv run python -c "import fastapi; print(fastapi.__version__)" 2>/dev/null; then
    echo ""
else
    echo -e "    ${RED}✗${NC} FastAPI not installed"
    ((ERRORS++))
fi

echo -n "  Checking Pydantic... "
if uv run python -c "import pydantic; print(pydantic.__version__)" 2>/dev/null; then
    echo ""
else
    echo -e "    ${RED}✗${NC} Pydantic not installed"
    ((ERRORS++))
fi

echo -n "  Checking cryptography... "
if uv run python -c "import cryptography; print(cryptography.__version__)" 2>/dev/null; then
    echo ""
else
    echo -e "    ${RED}✗${NC} cryptography not installed"
    ((ERRORS++))
fi

# -----------------------------------------------------------------------------
# Check environment configuration
# -----------------------------------------------------------------------------
echo ""
echo "Checking environment configuration..."

if [ -f ".env" ]; then
    echo -e "  ${GREEN}✓${NC} .env file found"
    
    # Check for required variables
    if grep -q "MCP_AUTH_TOKEN" .env 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} MCP_AUTH_TOKEN configured"
    else
        echo -e "  ${YELLOW}⚠${NC} MCP_AUTH_TOKEN not set in .env"
        ((WARNINGS++))
    fi
else
    echo -e "  ${YELLOW}⚠${NC} No .env file. Copy from .env.example"
    ((WARNINGS++))
fi

# -----------------------------------------------------------------------------
# Check data directories
# -----------------------------------------------------------------------------
echo ""
echo "Checking data directories..."

if [ -d "data/dataset" ]; then
    file_count=$(find data/dataset -type f -name "*.xlsx" -o -name "*.csv" 2>/dev/null | wc -l)
    echo -e "  ${GREEN}✓${NC} data/dataset exists ($file_count data files)"
else
    echo -e "  ${YELLOW}⚠${NC} data/dataset directory not found"
    ((WARNINGS++))
fi

if [ -d "results/data_dictionary_mappings" ]; then
    echo -e "  ${GREEN}✓${NC} results/data_dictionary_mappings exists"
else
    echo -e "  ${YELLOW}⚠${NC} results/data_dictionary_mappings not found"
    ((WARNINGS++))
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=== Verification Summary ==="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Environment is ready.${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ $WARNINGS warning(s), but environment is functional.${NC}"
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s) and $WARNINGS warning(s) found.${NC}"
    echo ""
    echo "To fix, run:"
    echo "  1. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  2. Install dependencies: uv sync --all-extras"
    echo "  3. Copy environment: cp .env.example .env"
    exit 1
fi
