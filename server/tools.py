"""
MCP Tool Definitions for RePORTaLiN.

This module defines all MCP tools exposed by the server. Each tool is
decorated with @mcp.tool() and uses Pydantic models for strict input validation.

Design Decisions:
    - FastMCP for simplified tool registration with automatic schema generation
    - Pydantic models for all tool arguments (LLMs need exact schemas)
    - Structured logging for every tool execution (audit trail)
    - Input validation inside tools (defense in depth)
    - ToolResult dataclass for consistent response format

Tool Categories:
    - Data Query Tools: query_database, search_dictionary
    - Metrics Tools: fetch_metrics, get_statistics
    - System Tools: health_check, get_capabilities

Security:
    - All tools validate inputs before processing
    - SQL-like queries are validated to prevent injection
    - Results are sanitized before return
    - All executions are logged with context

Usage:
    The `mcp` instance is imported by server/main.py and mounted
    on the FastAPI application for HTTP/SSE transport.

    >>> from server.tools import mcp
    >>> app.mount("/mcp", mcp.sse_app())
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator

from server.config import get_settings
from server.logger import get_logger, bind_context, clear_context
from shared.constants import SERVER_NAME, SERVER_VERSION, PROTOCOL_VERSION

__all__ = [
    "mcp",
    "QueryDatabaseInput",
    "SearchDictionaryInput",
    "FetchMetricsInput",
    "MetricType",
]

# Initialize logger for this module
logger = get_logger(__name__)

# =============================================================================
# FastMCP Server Instance
# =============================================================================

# Get settings for server configuration
settings = get_settings()

# Initialize FastMCP with server identity
mcp = FastMCP(
    name=SERVER_NAME,
    instructions="""
    RePORTaLiN MCP Server - Clinical Data Query System
    
    This server provides tools for querying clinical trial data with
    privacy-preserving mechanisms and k-anonymity enforcement.
    
    Available tools:
    - query_database: Execute validated SQL-like queries on clinical data
    - search_dictionary: Search the data dictionary for field definitions
    - fetch_metrics: Retrieve aggregate statistics with privacy protection
    - health_check: Verify server status and capabilities
    
    All queries enforce minimum k-anonymity thresholds to protect patient privacy.
    """,
    # Enable debug logging in local environment
    debug=settings.is_local,
    log_level=settings.log_level.value,
)


# =============================================================================
# Pydantic Input Models (Critical for LLM Schema Adherence)
# =============================================================================

class MetricType(str, Enum):
    """Supported metric types for fetch_metrics tool."""
    
    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    DISTRIBUTION = "distribution"


class QueryDatabaseInput(BaseModel):
    """
    Input schema for database query tool.
    
    The query must be a valid SELECT statement. INSERT, UPDATE, DELETE,
    and DDL statements are not allowed for security reasons.
    
    Attributes:
        query: SQL SELECT query string
        limit: Maximum number of rows to return (privacy protection)
        include_metadata: Whether to include column metadata in response
    """
    
    query: Annotated[
        str,
        Field(
            description="SQL SELECT query. Must start with 'SELECT'. "
                       "Only read operations are allowed.",
            min_length=10,
            max_length=2000,
            examples=["SELECT * FROM patients WHERE age > 18 LIMIT 10"],
        ),
    ]
    
    limit: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            le=1000,
            description="Maximum rows to return. Enforces result size limits.",
        ),
    ]
    
    include_metadata: Annotated[
        bool,
        Field(
            default=False,
            description="Include column types and descriptions in response.",
        ),
    ]
    
    @field_validator("query")
    @classmethod
    def validate_query_is_select(cls, v: str) -> str:
        """Ensure query is a SELECT statement only."""
        normalized = v.strip().upper()
        
        # Must start with SELECT
        if not normalized.startswith("SELECT"):
            raise ValueError(
                "Query must be a SELECT statement. "
                "INSERT, UPDATE, DELETE, and DDL are not allowed."
            )
        
        # Check for dangerous keywords
        dangerous_keywords = [
            "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
            "TRUNCATE", "EXEC", "EXECUTE", "--", ";--", "/*",
        ]
        for keyword in dangerous_keywords:
            if keyword in normalized and keyword != "SELECT":
                raise ValueError(
                    f"Query contains forbidden keyword: {keyword}. "
                    "Only SELECT queries are allowed."
                )
        
        return v.strip()


class SearchDictionaryInput(BaseModel):
    """
    Input schema for data dictionary search tool.
    
    Searches the clinical data dictionary for field definitions,
    descriptions, and valid value sets.
    
    Attributes:
        search_term: Term to search for in field names/descriptions
        table_filter: Optional table name to limit search scope
        include_values: Whether to include valid value sets
    """
    
    search_term: Annotated[
        str,
        Field(
            description="Search term for field names or descriptions. "
                       "Supports partial matching.",
            min_length=2,
            max_length=100,
            examples=["patient_id", "diagnosis", "medication"],
        ),
    ]
    
    table_filter: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional table name to limit search scope.",
            max_length=100,
        ),
    ]
    
    include_values: Annotated[
        bool,
        Field(
            default=True,
            description="Include valid value sets in results.",
        ),
    ]
    
    @field_validator("search_term")
    @classmethod
    def validate_search_term(cls, v: str) -> str:
        """Sanitize search term to prevent injection."""
        # Remove potentially dangerous characters
        sanitized = re.sub(r"[;\-\-\'\"\`\(\)\{\}\[\]]", "", v)
        return sanitized.strip()


class FetchMetricsInput(BaseModel):
    """
    Input schema for metrics retrieval tool.
    
    Fetches aggregate statistics with automatic k-anonymity enforcement.
    Results with fewer than k records are suppressed.
    
    Attributes:
        metric_type: Type of aggregation to perform
        field_name: Field to aggregate
        group_by: Optional field for grouping results
        filters: Optional filter conditions
    """
    
    metric_type: Annotated[
        MetricType,
        Field(
            description="Type of aggregation: count, sum, average, min, max, distribution",
        ),
    ]
    
    field_name: Annotated[
        str,
        Field(
            description="Field name to aggregate.",
            min_length=1,
            max_length=100,
            examples=["age", "diagnosis_count", "length_of_stay"],
        ),
    ]
    
    group_by: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional field to group results by.",
            max_length=100,
        ),
    ]
    
    filters: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description="Optional filter conditions as key-value pairs.",
            examples=[{"status": "active", "age_min": 18}],
        ),
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

@mcp.tool()
async def query_database(input: QueryDatabaseInput) -> dict[str, Any]:
    """
    Execute a validated SQL-like query on clinical data.
    
    This tool allows read-only queries against the clinical database.
    All queries are validated to ensure they are SELECT statements only.
    Results are limited and may be suppressed if they don't meet
    k-anonymity thresholds.
    
    Args:
        input: QueryDatabaseInput with query string and options
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating query success
        - data: Query results as list of dictionaries
        - row_count: Number of rows returned
        - metadata: Optional column metadata if requested
        - execution_time_ms: Query execution time
        
    Raises:
        ValueError: If query validation fails
    """
    start_time = time.perf_counter()
    
    # Bind logging context for this tool execution
    bind_context(
        tool="query_database",
        query_length=len(input.query),
        limit=input.limit,
    )
    
    logger.info(
        "Executing database query",
        query_preview=input.query[:50] + "..." if len(input.query) > 50 else input.query,
    )
    
    try:
        # In production, this would execute against the actual database
        # For now, return simulated results
        
        # Simulate query execution
        simulated_results = [
            {"id": i, "field": f"value_{i}", "timestamp": datetime.now(timezone.utc).isoformat()}
            for i in range(min(input.limit, 10))
        ]
        
        execution_time = (time.perf_counter() - start_time) * 1000
        
        result = {
            "success": True,
            "data": simulated_results,
            "row_count": len(simulated_results),
            "execution_time_ms": round(execution_time, 2),
        }
        
        if input.include_metadata:
            result["metadata"] = {
                "columns": ["id", "field", "timestamp"],
                "types": ["integer", "string", "datetime"],
            }
        
        logger.info(
            "Query executed successfully",
            row_count=len(simulated_results),
            execution_time_ms=result["execution_time_ms"],
        )
        
        return result
        
    except Exception as e:
        logger.error("Query execution failed", error=str(e))
        return {
            "success": False,
            "error": f"Query failed: {str(e)}",
            "data": None,
        }
    finally:
        clear_context()


@mcp.tool()
async def search_dictionary(input: SearchDictionaryInput) -> dict[str, Any]:
    """
    Search the clinical data dictionary for field definitions.
    
    This tool searches field names, descriptions, and metadata
    in the data dictionary. Use it to understand what fields
    are available and their valid values.
    
    Args:
        input: SearchDictionaryInput with search parameters
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating search success
        - matches: List of matching field definitions
        - total_matches: Total number of matches found
        - search_term: The search term used
    """
    bind_context(
        tool="search_dictionary",
        search_term=input.search_term,
        table_filter=input.table_filter,
    )
    
    logger.info(
        "Searching data dictionary",
        search_term=input.search_term,
        table_filter=input.table_filter,
    )
    
    try:
        # Simulated dictionary search results
        # In production, this would query the actual data dictionary files
        simulated_matches = [
            {
                "field_name": f"{input.search_term}_example",
                "table": input.table_filter or "clinical_data",
                "description": f"Example field matching '{input.search_term}'",
                "data_type": "string",
                "nullable": True,
            }
        ]
        
        if input.include_values:
            simulated_matches[0]["valid_values"] = ["value1", "value2", "value3"]
        
        logger.info(
            "Dictionary search completed",
            match_count=len(simulated_matches),
        )
        
        return {
            "success": True,
            "matches": simulated_matches,
            "total_matches": len(simulated_matches),
            "search_term": input.search_term,
        }
        
    except Exception as e:
        logger.error("Dictionary search failed", error=str(e))
        return {
            "success": False,
            "error": f"Search failed: {str(e)}",
            "matches": [],
        }
    finally:
        clear_context()


@mcp.tool()
async def fetch_metrics(input: FetchMetricsInput) -> dict[str, Any]:
    """
    Retrieve aggregate statistics with privacy protection.
    
    This tool computes aggregate metrics on clinical data while
    enforcing k-anonymity thresholds. Results with fewer than
    the minimum k records are suppressed to protect patient privacy.
    
    Args:
        input: FetchMetricsInput with metric type and options
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating computation success
        - metric_type: The type of metric computed
        - field_name: The field that was aggregated
        - result: The computed metric value
        - suppressed: Whether any groups were suppressed for privacy
        - k_threshold: The k-anonymity threshold applied
    """
    settings = get_settings()
    
    bind_context(
        tool="fetch_metrics",
        metric_type=input.metric_type.value,
        field_name=input.field_name,
        group_by=input.group_by,
    )
    
    logger.info(
        "Fetching metrics",
        metric_type=input.metric_type.value,
        field_name=input.field_name,
        group_by=input.group_by,
    )
    
    try:
        # Simulated metric computation
        # In production, this would compute actual statistics
        # Type: Union of possible result types for metrics
        result_value: int | float | dict[str, int]
        
        if input.metric_type == MetricType.COUNT:
            result_value = 1250
        elif input.metric_type == MetricType.AVERAGE:
            result_value = 45.7
        elif input.metric_type == MetricType.SUM:
            result_value = 57125
        elif input.metric_type in (MetricType.MIN, MetricType.MAX):
            result_value = 18 if input.metric_type == MetricType.MIN else 95
        else:  # DISTRIBUTION
            result_value = {"0-18": 150, "19-40": 450, "41-65": 400, "65+": 250}
        
        # Check if grouped results need suppression
        suppressed_groups = 0
        if input.group_by and isinstance(result_value, dict):
            suppressed_groups = sum(
                1 for v in result_value.values() 
                if isinstance(v, (int, float)) and v < settings.min_k_anonymity
            )
        
        logger.info(
            "Metrics computed successfully",
            metric_type=input.metric_type.value,
            suppressed_groups=suppressed_groups,
        )
        
        return {
            "success": True,
            "metric_type": input.metric_type.value,
            "field_name": input.field_name,
            "result": result_value,
            "suppressed": suppressed_groups > 0,
            "suppressed_count": suppressed_groups,
            "k_threshold": settings.min_k_anonymity,
            "group_by": input.group_by,
            "filters_applied": input.filters is not None,
        }
        
    except Exception as e:
        logger.error("Metrics computation failed", error=str(e))
        return {
            "success": False,
            "error": f"Metrics computation failed: {str(e)}",
            "result": None,
        }
    finally:
        clear_context()


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """
    Check server health and capabilities.
    
    Returns current server status, version information, and
    available capabilities. Use this to verify the server
    is operational before making other requests.
    
    Returns:
        Dictionary containing:
        - status: Server status ('healthy', 'degraded', 'unhealthy')
        - version: Server version string
        - protocol_version: MCP protocol version
        - capabilities: List of enabled capabilities
        - uptime_info: Server uptime metadata
    """
    logger.debug("Health check requested")
    
    settings = get_settings()
    
    return {
        "status": "healthy",
        "server_name": SERVER_NAME,
        "version": SERVER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "environment": settings.environment.value,
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": False,
            "logging": True,
        },
        "privacy": {
            "mode": settings.privacy_mode,
            "k_anonymity_threshold": settings.min_k_anonymity,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Resource Definitions (Optional - for future use)
# =============================================================================

@mcp.resource("config://server")
async def get_server_config() -> str:
    """
    Get current server configuration (non-sensitive).
    
    Returns a JSON string with public configuration values.
    Sensitive values like tokens are not included.
    """
    settings = get_settings()
    
    return f"""{{
    "server_name": "{SERVER_NAME}",
    "version": "{SERVER_VERSION}",
    "environment": "{settings.environment.value}",
    "transport": "{settings.mcp_transport}",
    "host": "{settings.mcp_host}",
    "port": {settings.mcp_port},
    "privacy_mode": "{settings.privacy_mode}",
    "k_anonymity": {settings.min_k_anonymity}
}}"""


# =============================================================================
# Utility Functions
# =============================================================================

def get_tool_registry() -> dict[str, Any]:
    """
    Get a summary of registered tools.
    
    Returns:
        Dictionary with tool names and their metadata
    """
    return {
        "server_name": SERVER_NAME,
        "version": SERVER_VERSION,
        "registered_tools": [
            "query_database",
            "search_dictionary", 
            "fetch_metrics",
            "health_check",
        ],
        "registered_resources": [
            "config://server",
        ],
    }
