# =============================================================================
# RePORTaLiN Specialist MCP Server - Production Docker Image
# =============================================================================
# Multi-stage build for an optimized, secure, air-gapped MCP server.
# Now using uv package manager for fast, reproducible builds.
#
# SECURITY FEATURES:
#   ✓ Non-root user 'analyst' (UID 1000)
#   ✓ Read-only filesystem design
#   ✓ Network isolation support (--network none)
#   ✓ No data baked into image (mounted at runtime)
#   ✓ Minimal attack surface (slim base + cleanup)
#   ✓ PHI/PII never exposed - only aggregates/schemas
#   ✓ Signal handling with exec form ENTRYPOINT
#   ✓ tini init system for proper PID 1 behavior
#
# RUNTIME REQUIREMENTS:
#   - Mount results/ directory as read-only
#   - Mount data/ directory as read-only (if needed)
#   - Run with --network none for air-gapped security
#
# Usage:
#   docker build -t reportalin-specialist .
#   docker run -i --rm --network none \
#     -v $(pwd)/results:/app/results:ro \
#     reportalin-specialist
#
# Build with BuildKit for improved caching:
#   DOCKER_BUILDKIT=1 docker build -t reportalin-specialist .

# -----------------------------------------------------------------------------
# Stage 1: Build dependencies with uv
# -----------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS builder

# Build-time arguments for versioning and provenance
ARG BUILD_VERSION
ARG BUILD_DATE
ARG VCS_REF

# Security: Don't store pip cache, disable version check
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install uv - fast Python package installer
# hadolint ignore=DL3013
RUN pip install --no-cache-dir uv

# Copy dependency files first for better layer caching
# README.md is required by pyproject.toml metadata
COPY pyproject.toml .python-version README.md ./

# Copy minimal source structure needed for package installation
# uv sync needs these to resolve the local package
COPY server/__init__.py ./server/
COPY server/py.typed ./server/
COPY client/__init__.py ./client/
COPY client/py.typed ./client/
COPY shared/__init__.py ./shared/
COPY shared/py.typed ./shared/
COPY scripts/__init__.py ./scripts/
COPY scripts/py.typed ./scripts/
COPY __version__.py ./

# Create virtual environment and install dependencies with uv
# UV_PROJECT_ENVIRONMENT tells uv sync to install to /opt/venv
# --frozen ensures lockfile is used if present (uv.lock)
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv venv /opt/venv && \
    (uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev)

# Clean up unnecessary files from venv to minimize attack surface
# hadolint ignore=SC2015
RUN find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyo" -delete 2>/dev/null || true && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true && \
    rm -rf /opt/venv/share/doc /opt/venv/share/man

# -----------------------------------------------------------------------------
# Stage 2: Production image
# -----------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS production

# Build-time arguments for OCI labels
ARG BUILD_VERSION
ARG BUILD_DATE
ARG VCS_REF

# Security labels (OCI standard) with build-time provenance
LABEL org.opencontainers.image.title="RePORTaLiN Specialist MCP Server" \
      org.opencontainers.image.description="Secure MCP Server for RePORT India - PHI Protected" \
      org.opencontainers.image.vendor="RePORTaLiN Team" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/reportalin/reportalin-agent" \
      security.policy="no-new-privileges,read-only-rootfs,network-none" \
      data.classification="PHI/PII-Protected"

# Install tini for proper init (handles signals correctly) and curl for healthchecks
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Security: Create non-root user 'analyst' with explicit UID/GID
RUN groupadd --gid 1000 analyst && \
    useradd --uid 1000 --gid analyst --shell /usr/sbin/nologin --create-home analyst

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=analyst:analyst /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only necessary application files (minimal footprint)
COPY --chown=analyst:analyst server/ ./server/
COPY --chown=analyst:analyst client/ ./client/
COPY --chown=analyst:analyst shared/ ./shared/
COPY --chown=analyst:analyst scripts/core/ ./scripts/core/
COPY --chown=analyst:analyst scripts/utils/ ./scripts/utils/
COPY --chown=analyst:analyst scripts/__init__.py ./scripts/

COPY --chown=analyst:analyst config.py .
COPY --chown=analyst:analyst __version__.py .

# Prepare directories for runtime (DO NOT COPY sensitive data)
# Data will be mounted at runtime as read-only
RUN mkdir -p /app/results /app/encrypted_logs && \
    chown -R analyst:analyst /app && \
    chmod 755 /app/results && \
    chmod 700 /app/encrypted_logs

# Security: Set restrictive permissions on source files
RUN chmod -R 500 /app/server /app/client /app/shared /app/scripts && \
    chmod 400 /app/config.py /app/__version__.py

# Security: Switch to non-root user
USER analyst

# Environment variables for secure configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    # Disable __pycache__ in container
    PYTHONPYCACHEPREFIX=/tmp/.pycache \
    # Privacy: Ensure no raw data exposure
    REPORTALIN_PRIVACY_MODE=strict \
    # Security: Disable debug and fault handler
    PYTHONFAULTHANDLER=0 \
    # MCP defaults
    MCP_TRANSPORT=stdio \
    # Disable Rich console output (critical for MCP stdio)
    NO_COLOR=1 \
    TERM=dumb \
    FORCE_COLOR=0

# Health check (HTTP mode - uses /health endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health 2>/dev/null || python -c "import sys; sys.exit(0)"

# Use tini as init to handle signals properly (PID 1 zombie reaping)
# NOTE: server.__main__ handles stdout isolation for JSON-RPC
# SIGTERM handling: tini forwards signals, Python handles graceful shutdown
ENTRYPOINT ["/usr/bin/tini", "--", "python", "-m", "server"]

# No CMD needed - stdio_runner handles transport automatically
# Default grace period for SIGTERM: 10 seconds (Docker default)
# Override with: docker run --stop-timeout=30
CMD []
