# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Enhanced MCP Tools (10 Total)**
  - `natural_language_query` - Answer complex multi-concept questions in plain English
  - `cohort_summary` - Comprehensive participant overview (Table 1 style)
  - `cross_tabulation` - Analyze relationships between two categorical variables
  - `variable_details` - Deep dive into one specific variable
  - `data_quality_report` - Missing data and completeness analysis
  - `multi_variable_comparison` - Side-by-side statistics for multiple variables

- **New MCP Resources (6 Total)**
  - `dictionary://codelists` - All codelist definitions
  - `dictionary://table/{name}` - Specific table schema
  - `dictionary://codelist/{name}` - Specific codelist values
  - `study://variables/{category}` - Variables by category

- **New MCP Prompts (4 Total)**
  - `research_question_template` - Research question guidance
  - `data_exploration_guide` - Data exploration steps
  - `statistical_analysis_template` - Statistical analysis patterns
  - `tb_outcome_analysis` - TB outcome specific guidance

### Changed

- **Tool Selection Behavior**
  - `combined_search` is now THE DEFAULT TOOL for ALL queries
  - Searches through ALL data sources (dictionary + cleaned + original datasets)
  - Use for any analytical question, counts, statistics, or distributions
  
- **`search_data_dictionary` Role Clarified**
  - Now explicitly for variable definitions ONLY (no statistics)
  - Use ONLY when asking "what variables exist?" or "what does variable X mean?"
  - For any analytical question, use `combined_search` instead

- Updated SYSTEM_INSTRUCTIONS with Tool Selection Guide
- Updated `dictionary://overview` resource with tool guidance
- Updated all documentation (README, MCP_SERVER_SETUP, TESTING_GUIDE)
- Updated test files to reflect 10 tools

## [2.1.0] - 2025-12-07

### Added

- **Security Hardening (Phase 1)**
  - AES-256-GCM encryption module replacing Fernet/AES-128
  - Async rate limiting with token bucket algorithm
  - Security headers middleware (CSP, HSTS, X-Frame-Options, etc.)
  - Input validation middleware for query string/parameter limits
  - Rotatable secrets for Zero Trust token rotation with grace periods
  - CORS hardening with environment-aware configuration
  
- **MCP Protocol Modernization (Phase 2)**
  - Updated to MCP Protocol version `2025-03-26`
  - Enhanced type system with `PrivacyMode`, `EnvironmentType`, `SecurityContext`
  - New `TransportType.STREAMABLE_HTTP` for latest MCP spec
  - Client retry logic with exponential backoff and jitter
  - `MCPRetryConfig` for configurable retry behavior
  - `connect_with_retry()` and `reconnect()` methods for resilience

- **CI/CD Automation (Phase 4)**
  - Comprehensive CI workflow (`.github/workflows/ci.yml`)
    - Multi-Python version testing (3.10-3.13)
    - Linting with Black and Ruff
    - Type checking with MyPy
    - Docker build verification
  - Release workflow (`.github/workflows/release.yml`)
    - Multi-platform Docker builds (amd64/arm64)
    - GitHub Container Registry publishing
    - Automated release notes
  - Security scanning workflow (`.github/workflows/security.yml`)
    - CodeQL analysis
    - Dependency vulnerability scanning
    - Container security with Trivy
    - Secret scanning with TruffleHog
    - SAST with Bandit

- **New Security Module** (`server/security/`)
  - `encryption.py` — AES-256-GCM with key derivation
  - `rate_limiter.py` — Async token bucket rate limiter
  - `middleware.py` — Security headers, input validation, rate limiting
  - `secrets.py` — Rotatable secrets with grace period support
  - Full `py.typed` marker for type checking

### Changed

- Bumped version to 2.1.0
- Updated `shared/constants.py` with 2025 protocol version and security constants
- Enhanced `shared/types.py` with comprehensive type definitions
- Refactored `server/main.py` to properly separate FastAPI routes from ASGI middleware
- Updated `server/auth.py` to use rotatable secrets for token rotation
- Updated `scripts/deidentify.py` with AES-256-GCM and Fernet fallback for legacy files
- Improved `client/mcp_client.py` with retry configuration and connection recovery

### Security

- All encryption now uses AES-256-GCM (NIST approved)
- Rate limiting prevents DoS attacks
- Security headers protect against common web vulnerabilities
- Input validation prevents oversized request attacks
- Token rotation supports Zero Trust architecture

## [2.0.0] - 2025-12-05

### Added

- `CONTRIBUTING.md` with development guidelines and PHI handling rules

### Changed

- Restructured all documentation to follow Diátaxis framework
- Updated `README.md` with GitHub admonitions and navigation anchors
- Enhanced `llms.txt` to match llms.txt specification

## [0.0.2] - 2025-12-04

### Added

- **MCP Server** — Model Context Protocol server for LLM integration
  - `get_study_variables` tool for natural language variable search
  - `generate_federated_code` tool for privacy-safe analysis code
  - `get_data_schema` tool for schema exploration
  - `get_aggregate_statistics` tool with k-anonymity protection
- **Encrypted Logging** — RSA-OAEP + AES-256-CBC hybrid encryption
  - `server/` for secure audit logging (Phase 1)
  - `scripts/core/log_decryptor.py` CLI for authorized decryption
  - Key rotation tracking (90-day NIST guideline)
  - PHI auto-redaction before encryption
- **Structured Logging** — JSON output with context support
  - `scripts/core/structured_logging.py` for log aggregation
  - Request-scoped context via `log_context()` context manager
- **Pydantic Configuration** — Type-safe settings management
  - `scripts/core/settings.py` with environment variable binding
  - Nested configuration groups (logging, encryption, MCP)
- **Privacy Aggregates** — K-anonymity protected data access
  - Minimum cell size of 5 for all aggregates
- **India DPDPA 2023 + DPDP Rules 2025 Compliance**
  - Aadhaar, PAN, ABHA, UHID pattern detection

### Changed

- Updated project structure with `/server/`, `/client/`, `/shared/` (MCP v2.0 architecture)
- Improved type hints throughout codebase

### Fixed

- Timezone-aware datetime handling in crypto_logger.py
- Added `__all__` exports to all public modules

## [0.0.1] - 2024-12-02

### Added

- Initial project setup
- Data extraction pipeline from Excel files
- De-identification engine for PHI/PII
- Country-specific privacy regulations (14 countries)
- Data dictionary loading and processing

[Unreleased]: https://github.com/your-org/RePORTaLiN-Agent/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/your-org/RePORTaLiN-Agent/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/your-org/RePORTaLiN-Agent/releases/tag/v0.0.1
