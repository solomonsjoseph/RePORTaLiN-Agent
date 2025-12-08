"""
Centralized Settings Module using Pydantic Settings.

This module provides type-safe, validated configuration management with:
- Environment variable support (.env files)
- Type coercion and validation
- Nested configuration models
- Secure secrets handling

Security Best Practices:
- All sensitive values are loaded from environment variables
- No secrets are logged or exposed in error messages
- Encryption keys are validated before use
- Paths are validated for safety

Usage:
    >>> from scripts.core import get_settings
    >>> settings = get_settings()
    >>> print(settings.log_level)
    'INFO'

    # Override via environment
    $ export REPORTALIN_LOG_LEVEL=DEBUG
    $ export REPORTALIN_VERBOSE=true

See Also:
    - https://docs.pydantic.dev/latest/concepts/pydantic_settings/
    - docs/MCP_SERVER_SETUP.md for deployment configuration
"""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Optional

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import central version for consistency
try:
    from __version__ import __version__ as PROJECT_VERSION
except ImportError:
    PROJECT_VERSION = "0.0.2"  # Fallback

# Public API
__all__ = [
    # Enums
    "LogLevel",
    "TransportMode",
    # Settings classes
    "Settings",
    "LoggingSettings",
    "EncryptionSettings",
    "MCPSettings",
    # Factory functions
    "get_settings",
    "reload_settings",
]


class LogLevel(str, Enum):
    """Valid log levels with string values."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def to_logging_level(self) -> int:
        """Convert to Python logging level integer."""
        return getattr(logging, self.value)


class TransportMode(str, Enum):
    """MCP transport modes."""

    STDIO = "stdio"
    SSE = "sse"


class EncryptionSettings(BaseSettings):
    """Encryption-specific settings for secure logging.

    Security Notes:
        - Private keys should NEVER be stored in code or committed to VCS
        - Use environment variables or secure secret managers
        - Keys are automatically validated on load
    """

    model_config = SettingsConfigDict(
        env_prefix="REPORTALIN_CRYPTO_",
        extra="ignore",
    )

    # Key management
    public_key_path: Optional[Path] = Field(
        default=None,
        description="Path to RSA public key for log encryption",
    )
    private_key_path: Optional[Path] = Field(
        default=None,
        description="Path to RSA private key for log decryption (maintainers only)",
    )
    private_key_password: Optional[SecretStr] = Field(
        default=None,
        description="Password for encrypted private key file",
    )

    # Key rotation
    key_rotation_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Days before key rotation warning",
    )

    # Developer access control
    authorized_key_fingerprints: list[str] = Field(
        default_factory=list,
        description="SHA256 fingerprints of authorized developer keys",
    )

    @field_validator("public_key_path", "private_key_path", mode="before")
    @classmethod
    def resolve_path(cls, v: Any) -> Optional[Path]:
        """Resolve and validate key paths."""
        if v is None:
            return None
        path = Path(v).expanduser().resolve()
        return path

    @field_validator("authorized_key_fingerprints", mode="before")
    @classmethod
    def parse_fingerprints(cls, v: Any) -> list[str]:
        """Parse fingerprints from comma-separated string or list."""
        if isinstance(v, str):
            return [f.strip() for f in v.split(",") if f.strip()]
        return v or []


class LoggingSettings(BaseSettings):
    """Logging-specific settings.

    Controls both standard logging and encrypted audit logging.
    """

    model_config = SettingsConfigDict(
        env_prefix="REPORTALIN_LOG_",
        extra="ignore",
    )

    # Basic logging
    level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Default log level",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose (DEBUG) logging with tree-view output",
    )
    simple_mode: bool = Field(
        default=False,
        description="Minimal console output (success/errors only)",
    )

    # Output configuration
    log_dir: Path = Field(
        default=Path(".logs"),
        description="Directory for standard log files",
    )
    encrypted_log_dir: Path = Field(
        default=Path("encrypted_logs"),
        description="Directory for encrypted audit logs",
    )

    # Structured logging
    json_format: bool = Field(
        default=False,
        description="Enable JSON-formatted log output",
    )
    include_timestamps: bool = Field(
        default=True,
        description="Include ISO timestamps in logs",
    )

    # Security
    redact_phi: bool = Field(
        default=True,
        description="Automatically redact PHI patterns in logs",
    )
    encrypt_sensitive: bool = Field(
        default=True,
        description="Encrypt logs containing sensitive operations",
    )

    @field_validator("log_dir", "encrypted_log_dir", mode="before")
    @classmethod
    def resolve_log_path(cls, v: Any) -> Path:
        """Resolve log directory paths."""
        if isinstance(v, str):
            return Path(v)
        return v

    @model_validator(mode="after")
    def set_verbose_level(self) -> "LoggingSettings":
        """Set DEBUG level when verbose is enabled."""
        if self.verbose:
            self.level = LogLevel.DEBUG
        return self


class MCPSettings(BaseSettings):
    """MCP server-specific settings.

    Security Configuration:
        - Default transport is stdio (most secure)
        - SSE mode binds only to localhost
        - k-anonymity threshold enforced for all aggregates
    """

    model_config = SettingsConfigDict(
        env_prefix="REPORTALIN_MCP_",
        extra="ignore",
    )

    # Transport configuration
    transport: TransportMode = Field(
        default=TransportMode.STDIO,
        description="MCP transport mode (stdio recommended for security)",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Host binding for SSE mode (localhost only for security)",
    )
    port: int = Field(
        default=8765,
        ge=1024,
        le=65535,
        description="Port for SSE mode",
    )

    # Privacy settings
    k_anonymity_threshold: int = Field(
        default=5,
        ge=1,
        description="Minimum cell size for k-anonymity protection",
    )
    allow_raw_data: bool = Field(
        default=False,
        description="SECURITY: Never enable in production - disables PHI protection",
    )

    # Server identity
    server_name: str = Field(
        default="RePORTaLiN-Specialist",
        description="MCP server display name",
    )
    server_version: str = Field(
        default=PROJECT_VERSION,
        description="MCP server version (auto-synced from __version__.py)",
    )

    @field_validator("host")
    @classmethod
    def validate_host_security(cls, v: str) -> str:
        """Enforce localhost binding for SSE mode."""
        allowed_hosts = {"127.0.0.1", "localhost", "::1"}
        if v not in allowed_hosts:
            import warnings

            warnings.warn(
                f"SECURITY WARNING: MCP host '{v}' is not localhost. "
                "This may expose the server to network attacks. "
                "Only use 127.0.0.1 or localhost in production.",
                stacklevel=2,
            )
        return v


class Settings(BaseSettings):
    """Main application settings with nested configuration groups.

    This is the central configuration object that aggregates all settings.
    Settings can be overridden via:
    1. Environment variables (REPORTALIN_* prefix)
    2. .env file in project root
    3. Programmatic override

    Environment Variable Examples:
        REPORTALIN_LOG_LEVEL=DEBUG
        REPORTALIN_LOG_VERBOSE=true
        REPORTALIN_MCP_TRANSPORT=stdio
        REPORTALIN_DATA_DIR=/custom/data/path

    Attributes:
        logging: Logging configuration
        encryption: Encryption/security settings
        mcp: MCP server settings
        data_dir: Data directory path
        results_dir: Results output directory
    """

    model_config = SettingsConfigDict(
        env_prefix="REPORTALIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # Nested settings groups
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    encryption: EncryptionSettings = Field(default_factory=EncryptionSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)

    # Path configuration (mirrors config.py for compatibility)
    root_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent,
        description="Project root directory",
    )
    data_dir: Optional[Path] = Field(
        default=None,
        description="Data directory path",
    )
    results_dir: Optional[Path] = Field(
        default=None,
        description="Results output directory",
    )
    dataset_name: str = Field(
        default="RePORTaLiN_sample",
        description="Name of the active dataset",
    )

    # Feature flags
    debug_mode: bool = Field(
        default=False,
        description="Enable debug features (never in production)",
    )

    # Class-level constants (not from env)
    DATASET_SUFFIXES: ClassVar[tuple[str, ...]] = ("_csv_files", "_files")
    DEFAULT_DATASET_NAME: ClassVar[str] = "RePORTaLiN_sample"

    @model_validator(mode="after")
    def resolve_paths(self) -> "Settings":
        """Resolve default paths relative to root_dir."""
        if self.data_dir is None:
            self.data_dir = self.root_dir / "data"
        if self.results_dir is None:
            self.results_dir = self.root_dir / "results"

        # Ensure log directories are absolute
        if not self.logging.log_dir.is_absolute():
            self.logging.log_dir = self.root_dir / self.logging.log_dir
        if not self.logging.encrypted_log_dir.is_absolute():
            self.logging.encrypted_log_dir = (
                self.root_dir / self.logging.encrypted_log_dir
            )

        return self

    @property
    def dataset_dir(self) -> Path:
        """Get the active dataset directory path."""
        return self.data_dir / "dataset" / self.dataset_name

    @property
    def clean_dataset_dir(self) -> Path:
        """Get the cleaned dataset output directory."""
        return self.results_dir / "dataset" / self.dataset_name

    @property
    def dictionary_json_output_dir(self) -> Path:
        """Get the data dictionary JSON output directory."""
        return self.results_dir / "data_dictionary_mappings"

    @property
    def dictionary_excel_file(self) -> Path:
        """Get the data dictionary Excel file path."""
        return (
            self.data_dir
            / "data_dictionary_and_mapping_specifications"
            / "RePORT_DEB_to_Tables_mapping.xlsx"
        )

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            self.results_dir,
            self.clean_dataset_dir,
            self.dictionary_json_output_dir,
            self.logging.log_dir,
            self.logging.encrypted_log_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def validate_config(self) -> list[str]:
        """Validate configuration and return list of warnings."""
        warnings = []

        if not self.data_dir.exists():
            warnings.append(f"Data directory not found: {self.data_dir}")

        if not self.dataset_dir.exists():
            warnings.append(f"Dataset directory not found: {self.dataset_dir}")

        if not self.dictionary_excel_file.exists():
            warnings.append(
                f"Data dictionary file not found: {self.dictionary_excel_file}"
            )

        # Security warnings
        if self.mcp.allow_raw_data:
            warnings.append(
                "SECURITY: allow_raw_data is enabled - PHI protection disabled!"
            )

        if self.debug_mode:
            warnings.append("DEBUG MODE is enabled - disable for production")

        return warnings

    def to_legacy_config(self) -> dict[str, Any]:
        """Export settings in legacy config.py format for compatibility.

        Returns:
            Dictionary with keys matching config.py module-level variables.
        """
        return {
            "ROOT_DIR": str(self.root_dir),
            "DATA_DIR": str(self.data_dir),
            "RESULTS_DIR": str(self.results_dir),
            "DATASET_DIR": str(self.dataset_dir),
            "DATASET_NAME": self.dataset_name,
            "CLEAN_DATASET_DIR": str(self.clean_dataset_dir),
            "DICTIONARY_EXCEL_FILE": str(self.dictionary_excel_file),
            "DICTIONARY_JSON_OUTPUT_DIR": str(self.dictionary_json_output_dir),
            "LOG_LEVEL": self.logging.level.to_logging_level(),
            "LOG_NAME": "reportalin-specialist",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings instance.

    Uses LRU cache to ensure singleton behavior. The settings are
    loaded once and reused across the application.

    Returns:
        Cached Settings instance.

    Example:
        >>> settings = get_settings()
        >>> settings.logging.level
        <LogLevel.INFO: 'INFO'>
    """
    return Settings()


def reload_settings() -> Settings:
    """Force reload of settings (clears cache).

    Use this when environment variables have changed and settings
    need to be reloaded.

    Returns:
        Fresh Settings instance.
    """
    get_settings.cache_clear()
    return get_settings()
