"""
MCP Tool Definitions for RePORTaLiN.

This module implements 10 secure tools for clinical data analysis:

1. search_data_dictionary - Search variable definitions, codelists, metadata
2. search_cleaned_dataset - Query de-identified cleaned data (aggregates only)
3. search_original_dataset - Query de-identified original data (aggregates only)
4. combined_search - Cross-reference dictionary with dataset for accurate answers
5. cross_tabulation - Analyze relationships between two variables
6. cohort_summary - Get comprehensive study overview
7. natural_language_query - Answer complex multi-concept questions
8. variable_details - Get comprehensive info about ONE specific variable
9. data_quality_report - Analyze missing data and completeness
10. multi_variable_comparison - Compare multiple variables side-by-side

Security Model:
    - NEVER expose raw data values or individual records
    - ONLY return aggregates, counts, summaries, and distributions
    - Variable names from dictionary are safe to expose
    - Actual data values are summarized, not returned directly

Data Sources:
    - ./results/data_dictionary_mappings/ - Variable definitions & codelists
    - ./results/deidentified/Indo-vap/cleaned/ - Cleaned de-identified data
    - ./results/deidentified/Indo-vap/original/ - Original de-identified data
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from server.config import get_settings
from server.logger import get_logger
from shared.constants import SERVER_NAME, SERVER_VERSION

__all__ = [
    "mcp",
    "get_tool_registry",
]

# Initialize logger
logger = get_logger(__name__)

# =============================================================================
# Path Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DICTIONARY_PATH = PROJECT_ROOT / "results" / "data_dictionary_mappings"
CLEANED_DATA_PATH = PROJECT_ROOT / "results" / "deidentified" / "Indo-vap" / "cleaned"
ORIGINAL_DATA_PATH = PROJECT_ROOT / "results" / "deidentified" / "Indo-vap" / "original"

# =============================================================================
# FastMCP Server Instance
# =============================================================================

settings = get_settings()

SYSTEM_INSTRUCTIONS = """
RePORTaLiN MCP Server - Secure Clinical Data Analysis for RePORT India TB Study

This server provides access to the RePORT India (Indo-VAP) tuberculosis cohort study data.
RePORT India is a multi-site prospective observational cohort studying TB treatment outcomes,
comorbidities (HIV, diabetes, malnutrition), and risk factors (smoking, alcohol) in India.

## IMPORTANT: Tool Selection Guide

**DEFAULT BEHAVIOR: Use `combined_search` for ALL queries unless specified otherwise.**

- For ANY analytical question → Use `combined_search`
- For counts, statistics, distributions → Use `combined_search`
- For "how many", "what percentage", "distribution" → Use `combined_search`
- ONLY for "what variables exist?" or "what does X mean?" → Use `search_data_dictionary`

## Available Tools (10 Total)

### PRIMARY TOOLS - Use for Most Questions

1. **combined_search** - THE DEFAULT TOOL FOR ALL QUERIES
   - Searches through ALL data sources (dictionary + cleaned + original datasets)
   - Automatically finds relevant variables AND retrieves statistics
   - USE FOR: Everything - "How many have diabetes?", "Age distribution", "HIV statistics"
   - This should be your FIRST choice for any question

2. **natural_language_query** - Answer complex multi-concept questions
   - Interprets complex questions and performs multi-variable analysis
   - USE FOR: "Compare outcomes between smokers and non-smokers", "HIV prevalence by site"

3. **cohort_summary** - Get comprehensive study overview
   - Demographics, comorbidities, risk factors, outcomes
   - Quick Table 1 style summary
   - USE FOR: "Give me an overview of the cohort"

4. **cross_tabulation** - Analyze relationships between two variables
   - Creates contingency tables with counts and percentages
   - USE FOR: "Is HIV associated with outcome?", "Sex distribution by site"

### DETAILED ANALYSIS TOOLS

5. **variable_details** - Get comprehensive info about ONE specific variable
   - Definition, codelist, statistics, and data quality metrics
   - USE FOR: "Tell me everything about the AGE variable"

6. **data_quality_report** - Analyze missing data and completeness
   - Flags variables with high missing rates
   - USE FOR: "What data quality issues exist?", "Which variables have missing data?"

7. **multi_variable_comparison** - Compare multiple variables side-by-side
   - Side-by-side statistics for multiple variables
   - USE FOR: "Compare AGE, BMI, and CD4 statistics"

### Supporting Tools (ONLY when specifically needed)

8. **search_data_dictionary** - Find variable definitions ONLY (NO statistics)
   - Use ONLY when user asks "what variables exist for X?" or "what does Y mean?"
   - DO NOT use for any analytical questions - use combined_search instead
   - Returns only metadata (names, descriptions, codelists)
   
9. **search_cleaned_dataset** - Query specific known variables directly
   - Use when you already know exact variable names and need targeted query
   - For general queries, prefer combined_search
   
10. **search_original_dataset** - Query original (pre-cleaning) data
    - Use only if cleaned data is missing something specific

## Available Resources (6 Total)

- `dictionary://overview` - Study data summary
- `dictionary://tables` - List of all tables
- `dictionary://codelists` - Categorical value definitions
- `dictionary://table/{name}` - Specific table schema
- `dictionary://codelist/{name}` - Specific codelist values
- `study://variables/{category}` - Variables by category (demographics, comorbidities, etc.)

## Available Prompts (4 Total)

- `research_question_template` - How to answer research questions
- `data_exploration_guide` - Step-by-step data exploration
- `statistical_analysis_template` - Conducting statistical analyses
- `tb_outcome_analysis` - TB treatment outcome specific guidance

## RePORT India Study Context

Common research areas:
- TB treatment outcomes (cure, failure, death, loss to follow-up)
- Comorbidities: HIV, diabetes mellitus, malnutrition/undernutrition
- Risk factors: smoking, alcohol use, BMI
- Demographics: age, sex, site
- Follow-up visits: baseline, month 2, 6, 12, 24

## Security Rules

- NEVER expose individual patient data
- ONLY report aggregate statistics (counts, means, percentages)
- Variable names are SAFE to share
- Raw values are summarized, not exposed directly
"""

mcp = FastMCP(
    name=SERVER_NAME,
    instructions=SYSTEM_INSTRUCTIONS,
    debug=settings.is_local,
    log_level=settings.log_level.value,
)


# =============================================================================
# Data Loading Functions
# =============================================================================

def load_data_dictionary() -> dict[str, list[dict]]:
    """Load all data dictionary JSONL files.

    Returns:
        Dictionary mapping table names to lists of field definition records.
        Empty dict if path doesn't exist or no files found.
    """
    all_data: dict[str, list[dict]] = {}
    
    if not DATA_DICTIONARY_PATH.exists():
        logger.warning(f"Data dictionary path not found: {DATA_DICTIONARY_PATH}")
        return all_data
    
    for jsonl_file in DATA_DICTIONARY_PATH.rglob("*.jsonl"):
        table_name = jsonl_file.stem
        records = []
        
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            all_data[table_name] = records
        except Exception as e:
            logger.error(f"Error loading {jsonl_file}: {e}")
    
    return all_data


def load_codelists() -> dict[str, list[dict]]:
    """Load all codelist definitions.

    Returns:
        Dictionary mapping codelist names to lists of code/descriptor records.
        Empty dict if codelist path doesn't exist.
    """
    codelists: dict[str, list[dict]] = {}
    codelist_path = DATA_DICTIONARY_PATH / "Codelists"
    
    if not codelist_path.exists():
        return codelists
    
    for jsonl_file in codelist_path.glob("*.jsonl"):
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        # Handle both field name formats
                        codelist_name = record.get("Codelist") or record.get("New codelists") or "UNKNOWN"
                        if codelist_name not in codelists:
                            codelists[codelist_name] = []
                        codelists[codelist_name].append(record)
        except Exception as e:
            logger.error(f"Error loading codelist {jsonl_file}: {e}")
    
    return codelists


def load_dataset(path: Path) -> dict[str, list[dict]]:
    """Load dataset from a directory of JSONL files.

    Args:
        path: Directory path containing JSONL files.

    Returns:
        Dictionary mapping table names (file stems) to lists of records.
        Empty dict if path doesn't exist.
    """
    dataset: dict[str, list[dict]] = {}
    
    if not path.exists():
        logger.warning(f"Dataset path not found: {path}")
        return dataset
    
    for jsonl_file in path.glob("*.jsonl"):
        table_name = jsonl_file.stem
        records = []
        
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            dataset[table_name] = records
        except Exception as e:
            logger.error(f"Error loading dataset {jsonl_file}: {e}")
    
    return dataset


# =============================================================================
# Cache
# =============================================================================

_dict_cache: dict[str, list[dict]] | None = None
_codelist_cache: dict[str, list[dict]] | None = None
_cleaned_cache: dict[str, list[dict]] | None = None
_original_cache: dict[str, list[dict]] | None = None


def get_data_dictionary() -> dict[str, list[dict]]:
    """Get cached data dictionary.

    Returns:
        Dictionary mapping table names to field definitions.
    """
    global _dict_cache
    if _dict_cache is None:
        _dict_cache = load_data_dictionary()
    return _dict_cache


def get_codelists() -> dict[str, list[dict]]:
    """Get cached codelists.

    Returns:
        Dictionary mapping codelist names to code/descriptor records.
    """
    global _codelist_cache
    if _codelist_cache is None:
        _codelist_cache = load_codelists()
    return _codelist_cache


def get_cleaned_dataset() -> dict[str, list[dict]]:
    """Get cached cleaned dataset.

    Returns:
        Dictionary mapping table names to de-identified records.
    """
    global _cleaned_cache
    if _cleaned_cache is None:
        _cleaned_cache = load_dataset(CLEANED_DATA_PATH)
    return _cleaned_cache


def get_original_dataset() -> dict[str, list[dict]]:
    """Get cached original dataset.

    Returns:
        Dictionary mapping table names to original de-identified records.
    """
    global _original_cache
    if _original_cache is None:
        _original_cache = load_dataset(ORIGINAL_DATA_PATH)
    return _original_cache


# =============================================================================
# Helper Functions for Secure Aggregation
# =============================================================================

def compute_variable_stats(records: list[dict], variable: str) -> dict[str, Any]:
    """
    Compute SAFE aggregate statistics for a variable.

    Returns counts, distributions - NEVER raw values.

    Args:
        records: List of data records to analyze.
        variable: Variable/field name to compute statistics for.

    Returns:
        Dictionary with aggregate statistics including type, counts,
        and either numeric statistics or categorical value counts.
    """
    values = [r.get(variable) for r in records if r.get(variable) is not None]
    
    if not values:
        return {"status": "no_data", "variable": variable}
    
    # Determine type
    numeric_values = []
    categorical_values = []
    
    for v in values:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            numeric_values.append(v)
        else:
            categorical_values.append(str(v))
    
    result = {
        "variable": variable,
        "total_records": len(records),
        "non_null_count": len(values),
        "null_count": len(records) - len(values),
        "null_percentage": round((len(records) - len(values)) / len(records) * 100, 1),
    }
    
    if numeric_values and len(numeric_values) > len(categorical_values):
        # Numeric variable - return statistics, NOT raw values
        result["type"] = "numeric"
        result["statistics"] = {
            "min": round(min(numeric_values), 2),
            "max": round(max(numeric_values), 2),
            "mean": round(statistics.mean(numeric_values), 2),
            "median": round(statistics.median(numeric_values), 2),
        }
        if len(numeric_values) > 1:
            result["statistics"]["std_dev"] = round(statistics.stdev(numeric_values), 2)
        
        # Provide distribution bins, NOT raw values
        result["distribution"] = compute_histogram(numeric_values)
    else:
        # Categorical variable - return value counts
        result["type"] = "categorical"
        counts = Counter(categorical_values)
        
        # Return top values with counts (safe aggregate)
        result["value_counts"] = [
            {"value": k, "count": v, "percentage": round(v / len(values) * 100, 1)}
            for k, v in counts.most_common(20)  # Limit to top 20
        ]
        result["unique_values"] = len(counts)
    
    return result


def compute_histogram(values: list[float], bins: int = 10) -> list[dict]:
    """Compute histogram bins for numeric data.

    Args:
        values: List of numeric values to bin.
        bins: Number of histogram bins (default: 10).

    Returns:
        List of dicts with 'range' and 'count' keys for each bin.
    """
    if not values:
        return []
    
    min_val, max_val = min(values), max(values)
    if min_val == max_val:
        return [{"range": f"{min_val}", "count": len(values)}]
    
    bin_width = (max_val - min_val) / bins
    histogram = []
    
    for i in range(bins):
        bin_start = min_val + i * bin_width
        bin_end = bin_start + bin_width
        count = sum(1 for v in values if bin_start <= v < bin_end)
        if i == bins - 1:  # Last bin includes max
            count = sum(1 for v in values if bin_start <= v <= bin_end)
        
        histogram.append({
            "range": f"{round(bin_start, 1)}-{round(bin_end, 1)}",
            "count": count
        })
    
    return histogram


def find_variable_in_dataset(dataset: dict[str, list[dict]], variable: str) -> list[tuple[str, list[dict]]]:
    """Find which tables contain a variable.

    Args:
        dataset: Dataset dictionary mapping table names to records.
        variable: Variable name to search for (case-insensitive partial match).

    Returns:
        List of tuples containing (table_name, matched_key, records) for each match.
    """
    matches = []
    var_lower = variable.lower()
    
    for table_name, records in dataset.items():
        if records:
            # Check if variable exists in this table
            sample = records[0]
            for key in sample.keys():
                if var_lower in key.lower():
                    matches.append((table_name, key, records))
                    break
    
    return matches


# =============================================================================
# Input Models
# =============================================================================

class DictionarySearchInput(BaseModel):
    """Input for searching the data dictionary."""
    
    query: Annotated[
        str,
        Field(
            description="Search term for variable names, descriptions, or codelists. "
                       "Examples: 'HIV', 'age', 'smoking', 'SEX codelist', 'outcome'",
            min_length=1,
            max_length=200,
        ),
    ]
    
    include_codelists: Annotated[
        bool,
        Field(default=True, description="Include codelist searches"),
    ]


class DatasetSearchInput(BaseModel):
    """Input for searching datasets."""
    
    variable: Annotated[
        str,
        Field(
            description="Variable name to analyze. Use search_data_dictionary first to find exact names. "
                       "Examples: 'AGE', 'SEX', 'SMOKHX', 'HIV_R'",
        ),
    ]
    
    table_filter: Annotated[
        str | None,
        Field(default=None, description="Optional: limit to specific table"),
    ]


class CombinedSearchInput(BaseModel):
    """Input for combined dictionary + dataset search."""
    
    concept: Annotated[
        str,
        Field(
            description="Clinical concept to analyze. "
                       "Examples: 'smoking status', 'age distribution', 'HIV status', 'TB outcome'",
        ),
    ]
    
    include_statistics: Annotated[
        bool,
        Field(default=True, description="Include dataset statistics if variable found"),
    ]


class CrossTabulationInput(BaseModel):
    """Input for cross-tabulation analysis between two variables."""
    
    variable1: Annotated[
        str,
        Field(
            description="First variable for cross-tabulation. "
                       "Examples: 'SEX', 'HIV_R', 'SMOKHX', 'OUTCOME'",
        ),
    ]
    
    variable2: Annotated[
        str,
        Field(
            description="Second variable for cross-tabulation. "
                       "Examples: 'OUTCOME', 'DM_R', 'SITE'",
        ),
    ]
    
    table_filter: Annotated[
        str | None,
        Field(default=None, description="Optional: limit to specific table"),
    ]


class CohortSummaryInput(BaseModel):
    """Input for cohort summary generation."""
    
    include_demographics: Annotated[
        bool,
        Field(default=True, description="Include demographic breakdown (age, sex)"),
    ]
    
    include_comorbidities: Annotated[
        bool,
        Field(default=True, description="Include comorbidity statistics (HIV, diabetes)"),
    ]
    
    include_outcomes: Annotated[
        bool,
        Field(default=True, description="Include treatment outcome statistics"),
    ]
    
    include_risk_factors: Annotated[
        bool,
        Field(default=True, description="Include risk factors (smoking, alcohol)"),
    ]


class NaturalLanguageQueryInput(BaseModel):
    """Input for natural language queries about the clinical data."""
    
    question: Annotated[
        str,
        Field(
            description="Natural language question about the clinical data. "
                       "Examples: 'How many participants have both HIV and diabetes?', "
                       "'What percentage of smokers had unfavorable outcomes?', "
                       "'Compare age distribution between males and females'",
            min_length=5,
            max_length=500,
        ),
    ]
    
    max_results: Annotated[
        int,
        Field(default=10, ge=1, le=50, description="Maximum number of variables to analyze"),
    ]


class VariableDetailsInput(BaseModel):
    """Input for getting detailed information about a specific variable."""
    
    variable_name: Annotated[
        str,
        Field(
            description="Exact variable name to get details for. "
                       "Use search_data_dictionary first to find exact names.",
        ),
    ]
    
    include_codelist: Annotated[
        bool,
        Field(default=True, description="Include codelist values if applicable"),
    ]
    
    include_statistics: Annotated[
        bool,
        Field(default=True, description="Include aggregate statistics from dataset"),
    ]


class DataQualityReportInput(BaseModel):
    """Input for generating data quality report."""
    
    table_filter: Annotated[
        str | None,
        Field(default=None, description="Optional: limit to specific table"),
    ]
    
    variables: Annotated[
        list[str] | None,
        Field(default=None, description="Optional: specific variables to check. If None, checks all."),
    ]
    
    threshold_missing: Annotated[
        float,
        Field(default=10.0, ge=0, le=100, description="Flag variables with missing % above this threshold"),
    ]


class MultiVariableComparisonInput(BaseModel):
    """Input for comparing statistics across multiple variables."""
    
    variables: Annotated[
        list[str],
        Field(
            description="List of variable names to compare. "
                       "Examples: ['AGE', 'BMI', 'CD4'] or ['HIV_R', 'DM_R', 'SMOKHX']",
            min_length=2,
            max_length=10,
        ),
    ]
    
    table_filter: Annotated[
        str | None,
        Field(default=None, description="Optional: limit to specific table"),
    ]


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
async def search_data_dictionary(
    input: DictionarySearchInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Search ONLY for variable definitions and metadata - NO statistics.
    
    USE THIS TOOL ONLY WHEN:
    - User specifically asks "what variables exist for X?"
    - User asks "what does variable Y mean?"
    - User wants to know field names, data types, or codelist values
    - User needs ONLY metadata without any statistics
    
    DO NOT USE THIS TOOL WHEN:
    - User asks for counts, distributions, or statistics (use combined_search instead)
    - User asks "how many patients have X?" (use combined_search instead)
    - User asks any analytical question (use combined_search instead)
    
    This returns ONLY variable metadata (names, descriptions, codelists).
    For statistics or analysis, use combined_search instead.
    
    Args:
        input: Search parameters
        ctx: MCP context
    
    Returns:
        Matching variables and codelists from the data dictionary (metadata only)
    """
    await ctx.info(f"Searching data dictionary for: {input.query}")
    
    try:
        data_dict = get_data_dictionary()
        codelists = get_codelists() if input.include_codelists else {}
        
        query_lower = input.query.lower()
        
        # Search variables
        variable_matches = []
        for table_name, records in data_dict.items():
            for record in records:
                searchable = " ".join([
                    str(record.get("Question Short Name (Databank Fieldname)", "")),
                    str(record.get("Question", "")),
                    str(record.get("Module", "")),
                    str(record.get("Code List or format", "")),
                    str(record.get("Notes", "")),
                ]).lower()
                
                if query_lower in searchable:
                    variable_matches.append({
                        "table": record.get("__table__", table_name),
                        "field_name": record.get("Question Short Name (Databank Fieldname)"),
                        "description": record.get("Question"),
                        "type": record.get("Type"),
                        "codelist_ref": record.get("Code List or format"),
                        "module": record.get("Module"),
                        "form": record.get("Form"),
                    })
        
        # Search codelists
        codelist_matches = []
        if input.include_codelists:
            for name, values in codelists.items():
                if query_lower in name.lower():
                    codelist_matches.append({
                        "codelist_name": name,
                        "values": [
                            {"code": v.get("Codes"), "description": v.get("Descriptors")}
                            for v in values
                        ],
                    })
                else:
                    # Search in descriptors
                    for v in values:
                        if query_lower in str(v.get("Descriptors", "")).lower():
                            codelist_matches.append({
                                "codelist_name": name,
                                "values": [
                                    {"code": val.get("Codes"), "description": val.get("Descriptors")}
                                    for val in values
                                ],
                            })
                            break
        
        # Deduplicate codelist matches
        seen = set()
        unique_codelists = []
        for cl in codelist_matches:
            if cl["codelist_name"] not in seen:
                seen.add(cl["codelist_name"])
                unique_codelists.append(cl)
        
        return {
            "query": input.query,
            "variables_found": len(variable_matches),
            "variables": variable_matches[:50],  # Limit results
            "codelists_found": len(unique_codelists),
            "codelists": unique_codelists[:10],
            "hint": "Use exact field_name values when querying datasets",
        }
        
    except Exception as e:
        logger.error(f"Dictionary search failed: {e}")
        return {"error": str(e), "query": input.query}


@mcp.tool()
async def search_cleaned_dataset(
    input: DatasetSearchInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Search the CLEANED de-identified dataset for aggregate statistics.
    
    SECURITY: Returns ONLY aggregates (counts, means, distributions).
    NEVER returns individual patient records.
    
    Use this to answer questions like:
    - "What is the age distribution?"
    - "How many participants are male vs female?"
    - "What percentage have HIV?"
    
    Args:
        input: Variable to analyze
        ctx: MCP context
    
    Returns:
        Aggregate statistics for the variable (counts, percentages, distributions)
    """
    await ctx.info(f"Searching cleaned dataset for: {input.variable}")
    
    try:
        dataset = get_cleaned_dataset()
        
        if not dataset:
            return {"error": "Cleaned dataset not available"}
        
        var_lower = input.variable.lower()
        results = {
            "variable_searched": input.variable,
            "dataset": "cleaned",
            "tables_analyzed": [],
            "aggregates": [],
        }
        
        for table_name, records in dataset.items():
            if input.table_filter and input.table_filter.lower() not in table_name.lower():
                continue
            
            if not records:
                continue
            
            # Find matching variables in this table
            sample = records[0]
            matching_vars = [k for k in sample.keys() if var_lower in k.lower()]
            
            for var in matching_vars:
                stats = compute_variable_stats(records, var)
                stats["table"] = table_name
                results["aggregates"].append(stats)
                results["tables_analyzed"].append(table_name)
        
        results["tables_analyzed"] = list(set(results["tables_analyzed"]))
        results["total_matches"] = len(results["aggregates"])
        
        if not results["aggregates"]:
            return {
                "variable_searched": input.variable,
                "status": "not_found",
                "suggestion": "Use search_data_dictionary first to find exact variable names",
            }
        
        return results
        
    except Exception as e:
        logger.error(f"Cleaned dataset search failed: {e}")
        return {"error": str(e)}


@mcp.tool()
async def search_original_dataset(
    input: DatasetSearchInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Search the ORIGINAL de-identified dataset for aggregate statistics.
    
    SECURITY: Returns ONLY aggregates (counts, means, distributions).
    NEVER returns individual patient records.
    
    Use this when:
    - Cleaned dataset doesn't have the variable
    - You need to compare cleaned vs original
    - Looking for variables that may have been modified in cleaning
    
    Args:
        input: Variable to analyze
        ctx: MCP context
    
    Returns:
        Aggregate statistics for the variable (counts, percentages, distributions)
    """
    await ctx.info(f"Searching original dataset for: {input.variable}")
    
    try:
        dataset = get_original_dataset()
        
        if not dataset:
            return {"error": "Original dataset not available"}
        
        var_lower = input.variable.lower()
        results = {
            "variable_searched": input.variable,
            "dataset": "original",
            "tables_analyzed": [],
            "aggregates": [],
        }
        
        for table_name, records in dataset.items():
            if input.table_filter and input.table_filter.lower() not in table_name.lower():
                continue
            
            if not records:
                continue
            
            # Find matching variables in this table
            sample = records[0]
            matching_vars = [k for k in sample.keys() if var_lower in k.lower()]
            
            for var in matching_vars:
                stats = compute_variable_stats(records, var)
                stats["table"] = table_name
                results["aggregates"].append(stats)
                results["tables_analyzed"].append(table_name)
        
        results["tables_analyzed"] = list(set(results["tables_analyzed"]))
        results["total_matches"] = len(results["aggregates"])
        
        if not results["aggregates"]:
            return {
                "variable_searched": input.variable,
                "status": "not_found",
                "suggestion": "Use search_data_dictionary first to find exact variable names",
            }
        
        return results
        
    except Exception as e:
        logger.error(f"Original dataset search failed: {e}")
        return {"error": str(e)}


@mcp.tool()
async def combined_search(
    input: CombinedSearchInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    PRIMARY TOOL: Answer ANY question about the RePORT India TB study data.
    
    THIS IS THE DEFAULT TOOL FOR ALL QUERIES. Always use this tool unless the
    user specifically asks ONLY about variable definitions/metadata.
    
    This tool searches through ALL data sources:
    1. DATA DICTIONARY - Finds relevant variables for your concept
    2. CLEANED DATASET - Gets aggregate statistics (counts, means, distributions)
    3. ORIGINAL DATASET - Falls back if cleaned data is unavailable
    4. CODELISTS - Returns valid values for categorical variables
    
    Use this for ANY analytical question:
    - "How many participants have diabetes?" → Statistics from dataset
    - "What is the smoking status distribution?" → Counts and percentages
    - "Show me HIV-related data" → Variables + statistics
    - "What are the treatment outcomes?" → Outcome distributions
    - "Age and sex distribution" → Demographics summary
    - "BMI/malnutrition data" → Numerical statistics
    - "Compare outcomes by HIV status" → Cross-analysis
    
    SECURITY: Returns ONLY aggregate statistics. NEVER individual records.
    
    Args:
        input: Clinical concept, research question, or variable name to analyze
        ctx: MCP context
    
    Returns:
        Variables found in dictionary + aggregate statistics from ALL datasets
    """
    await ctx.info(f"Combined search for: {input.concept}")
    
    try:
        data_dict = get_data_dictionary()
        codelists = get_codelists()
        cleaned_dataset = get_cleaned_dataset()
        original_dataset = get_original_dataset()
        
        concept_lower = input.concept.lower()
        
        # =================================================================
        # STEP 1: Build comprehensive search terms from the concept
        # =================================================================
        
        # RePORT India specific synonyms and related terms
        # NOTE: Avoid short terms (2 chars) that match too broadly
        concept_synonyms = {
            # Demographics
            "age": ["age", "birth", "dob", "years old"],
            "sex": ["sex", "gender", "male", "female"],
            "site": ["site", "center", "location", "pune", "chennai", "vellore"],
            
            # Anthropometrics & Nutrition
            "bmi": ["bmi", "body mass", "weight", "height"],
            "weight": ["weight", "kgs", "mass"],
            "height": ["height", "tall"],
            "malnutrition": ["malnutrition", "undernutrition", "undernourish", "bmi", "weight"],
            "nutrition": ["nutrition", "bmi", "weight", "diet", "food"],
            
            # Comorbidities - be specific to avoid false matches
            "diabetes": ["diabetes", "diabetic", "glucose", "hba1c", "hba1", "fbg_", "rbg_", "ogtt", "blood sugar"],
            "hiv": ["hiv", "aids", "hivstat", "retroviral", "antiretroviral"],
            
            # Risk factors
            "smoking": ["smoking", "smoke", "smoker", "tobacco", "cigarette", "smokhx", "bidi"],
            "alcohol": ["alcohol", "drinking", "drink", "liquor", "beer", "alcoh"],
            "drug": ["drug use", "substance", "injection drug", "idu"],
            
            # TB specific
            "tuberculosis": ["tuberculosis", "tbnew", "tbdx", "pulmonary"],
            "diagnosis": ["diagnosis", "diagnosed", "tbdx", "confirm"],
            "treatment": ["treatment", "therapy", "regimen", "medication", "anti-tb"],
            "outcome": ["outcome", "outclin", "outoth", "cure", "fail", "death", "ltfu", "treatment result"],
            "cure": ["cure", "cured", "success", "favorable"],
            "failure": ["failure", "fail", "unfavorable", "unsuccessful"],
            "death": ["death", "died", "mortality", "dead"],
            "relapse": ["relapse", "recurrence", "recurrent", "recur"],
            "follow-up": ["follow", "followup", "fua_", "fub_", "visit"],
            
            # Lab tests
            "sputum": ["sputum", "smear", "afb", "microscopy"],
            "culture": ["culture", "growth"],
            "xpert": ["xpert", "genexpert", "pcr", "molecular"],
            "xray": ["xray", "x-ray", "chest", "radiograph", "cxr"],
            "cd4": ["cd4", "t-cell", "immune"],
            
            # Clinical
            "symptoms": ["symptom", "cough", "fever", "weight loss", "night sweat"],
            "cough": ["cough", "sputum", "expectoration"],
            "fever": ["fever", "temperature", "febrile"],
            
            # Time points
            "baseline": ["baseline", "enrollment", "initial", "screening", "index"],
            "month": ["month", "week", "day", "visit", "follow"],
        }
        
        # Build search terms from the query
        search_terms = set()
        search_terms.add(concept_lower)
        
        # Add individual words from the query
        for word in concept_lower.split():
            if len(word) > 2:  # Skip very short words
                search_terms.add(word)
        
        # Add synonyms for matching concepts
        for key, synonyms in concept_synonyms.items():
            if key in concept_lower or any(syn in concept_lower for syn in synonyms):
                search_terms.update(synonyms)
        
        search_terms = list(search_terms)[:15]  # Limit to avoid too broad search
        
        # =================================================================
        # STEP 2: Search DATA DICTIONARY (actual search, not guessing)
        # =================================================================
        
        results = {
            "concept": input.concept,
            "search_terms_used": search_terms,
            "variables_found": [],
            "codelists_found": [],
            "statistics": [],
            "data_source": None,
            "summary": {},
        }
        
        # Search through all data dictionary tables
        found_vars = {}  # field_name -> info
        for table_name, records in data_dict.items():
            for record in records:
                # Build searchable text from all relevant fields
                field_name = record.get("Question Short Name (Databank Fieldname)", "")
                searchable_parts = [
                    str(field_name),
                    str(record.get("Question", "")),
                    str(record.get("Module", "")),
                    str(record.get("Code List or format", "")),
                    str(record.get("Notes", "")),
                ]
                searchable = " ".join(searchable_parts).lower()
                
                # Check if any search term matches
                for term in search_terms:
                    if term in searchable:
                        if field_name and field_name not in found_vars:
                            found_vars[field_name] = {
                                "field_name": field_name,
                                "description": record.get("Question"),
                                "type": record.get("Type"),
                                "table": record.get("__table__", table_name),
                                "module": record.get("Module"),
                                "codelist_ref": record.get("Code List or format"),
                                "matched_term": term,
                            }
                        break
        
        results["variables_found"] = list(found_vars.values())[:30]  # Limit results
        
        # =================================================================
        # STEP 3: Search CODELISTS for matching values
        # =================================================================
        
        found_codelists = {}
        for name, values in codelists.items():
            name_lower = name.lower()
            # Check if codelist name matches any search term
            for term in search_terms:
                if term in name_lower:
                    if name not in found_codelists:
                        found_codelists[name] = {
                            "name": name,
                            "values": [
                                {"code": v.get("Codes"), "description": v.get("Descriptors")}
                                for v in values[:15]  # Limit values shown
                            ],
                            "total_values": len(values),
                        }
                    break
            
            # Also check if any value descriptions match
            if name not in found_codelists:
                for v in values:
                    desc = str(v.get("Descriptors", "")).lower()
                    for term in search_terms:
                        if term in desc:
                            found_codelists[name] = {
                                "name": name,
                                "values": [
                                    {"code": val.get("Codes"), "description": val.get("Descriptors")}
                                    for val in values[:15]
                                ],
                                "total_values": len(values),
                            }
                            break
                    if name in found_codelists:
                        break
        
        results["codelists_found"] = list(found_codelists.values())[:10]
        
        # =================================================================
        # STEP 4: Get STATISTICS from datasets (cleaned first, then original)
        # =================================================================
        
        if input.include_statistics:
            stats_computed = {}  # actual_field -> stats
            
            # Try cleaned dataset first
            data_source = "cleaned"
            for var_info in results["variables_found"][:15]:
                field_name = var_info["field_name"]
                if not field_name:
                    continue
                
                field_lower = field_name.lower()
                found_in_cleaned = False
                
                # Search in cleaned dataset
                for table_name, records in cleaned_dataset.items():
                    if not records:
                        continue
                    
                    sample = records[0]
                    
                    # Try exact match first
                    if field_name in sample:
                        if field_name not in stats_computed:
                            stats = compute_variable_stats(records, field_name)
                            stats["source_table"] = table_name
                            stats["source_dataset"] = "cleaned"
                            stats["dictionary_field"] = field_name
                            stats["match_type"] = "exact"
                            stats_computed[field_name] = stats
                            found_in_cleaned = True
                            break
                    
                    # Try partial match (handles prefixed fields)
                    for actual_field in sample.keys():
                        actual_lower = actual_field.lower()
                        if (field_lower in actual_lower or 
                            actual_lower.endswith(field_lower) or
                            field_lower.endswith(actual_lower)):
                            if actual_field not in stats_computed:
                                stats = compute_variable_stats(records, actual_field)
                                stats["source_table"] = table_name
                                stats["source_dataset"] = "cleaned"
                                stats["dictionary_field"] = field_name
                                stats["actual_field"] = actual_field
                                stats["match_type"] = "partial"
                                stats_computed[actual_field] = stats
                                found_in_cleaned = True
                                break
                    
                    if found_in_cleaned:
                        break
                
                # If not found in cleaned, try original dataset
                if not found_in_cleaned and original_dataset:
                    for table_name, records in original_dataset.items():
                        if not records:
                            continue
                        
                        sample = records[0]
                        
                        # Try exact match
                        if field_name in sample:
                            if field_name not in stats_computed:
                                stats = compute_variable_stats(records, field_name)
                                stats["source_table"] = table_name
                                stats["source_dataset"] = "original"
                                stats["dictionary_field"] = field_name
                                stats["match_type"] = "exact"
                                stats_computed[field_name] = stats
                                data_source = "original (not in cleaned)"
                                break
                        
                        # Try partial match
                        for actual_field in sample.keys():
                            actual_lower = actual_field.lower()
                            if (field_lower in actual_lower or 
                                actual_lower.endswith(field_lower)):
                                if actual_field not in stats_computed:
                                    stats = compute_variable_stats(records, actual_field)
                                    stats["source_table"] = table_name
                                    stats["source_dataset"] = "original"
                                    stats["dictionary_field"] = field_name
                                    stats["actual_field"] = actual_field
                                    stats["match_type"] = "partial"
                                    stats_computed[actual_field] = stats
                                    data_source = "original (not in cleaned)"
                                    break
                
                # Limit total statistics
                if len(stats_computed) >= 8:
                    break
            
            results["statistics"] = list(stats_computed.values())
            results["data_source"] = data_source if stats_computed else "no data found"
        
        # =================================================================
        # STEP 5: Build summary
        # =================================================================
        
        results["summary"] = {
            "query": input.concept,
            "variables_found": len(results["variables_found"]),
            "codelists_found": len(results["codelists_found"]),
            "statistics_computed": len(results["statistics"]),
            "data_source": results["data_source"],
        }
        
        # Add guidance if nothing found
        if not results["variables_found"]:
            results["guidance"] = (
                f"No variables found for '{input.concept}'. "
                "Try:\n"
                "- Different keywords (e.g., 'smoking' instead of 'tobacco use')\n"
                "- Medical abbreviations (e.g., 'DM' for diabetes, 'HIV' for human immunodeficiency virus)\n"
                "- Specific variable names if you know them\n"
                "- Use search_data_dictionary to browse all available variables"
            )
        
        return results
        
    except Exception as e:
        logger.error(f"Combined search failed: {e}")
        return {"error": str(e), "concept": input.concept}


@mcp.tool()
async def cross_tabulation(
    input: CrossTabulationInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Create a cross-tabulation (contingency table) between two categorical variables.
    
    Returns aggregate counts showing the relationship between variables.
    Useful for understanding associations in the data, such as:
    - HIV status vs treatment outcome
    - Sex vs smoking status
    - Diabetes status vs age group
    
    SECURITY: Returns ONLY aggregate counts. NEVER individual records.
    
    Args:
        input: Two variables to cross-tabulate
        ctx: MCP context
    
    Returns:
        Contingency table with counts and percentages
    """
    await ctx.info(f"Creating cross-tabulation: {input.variable1} x {input.variable2}")
    
    try:
        dataset = get_cleaned_dataset()
        
        if not dataset:
            return {"error": "Dataset not available"}
        
        var1_lower = input.variable1.lower()
        var2_lower = input.variable2.lower()
        
        results = {
            "variable1": input.variable1,
            "variable2": input.variable2,
            "cross_tabulations": [],
            "summary": {},
        }
        
        for table_name, records in dataset.items():
            if input.table_filter and input.table_filter.lower() not in table_name.lower():
                continue
            
            if not records:
                continue
            
            sample = records[0]
            
            # Find matching variables
            var1_match = None
            var2_match = None
            
            for key in sample.keys():
                key_lower = key.lower()
                if var1_lower in key_lower and var1_match is None:
                    var1_match = key
                if var2_lower in key_lower and var2_match is None:
                    var2_match = key
            
            if var1_match and var2_match and var1_match != var2_match:
                # Build contingency table
                contingency: dict[str, dict[str, int]] = {}
                total_count = 0
                
                for record in records:
                    val1 = str(record.get(var1_match, "Unknown"))
                    val2 = str(record.get(var2_match, "Unknown"))
                    
                    if val1 not in contingency:
                        contingency[val1] = {}
                    if val2 not in contingency[val1]:
                        contingency[val1][val2] = 0
                    contingency[val1][val2] += 1
                    total_count += 1
                
                # Convert to structured output
                rows = []
                var1_totals: dict[str, int] = {}
                var2_totals: dict[str, int] = {}
                
                for val1, val2_counts in sorted(contingency.items()):
                    row_total = sum(val2_counts.values())
                    var1_totals[val1] = row_total
                    
                    for val2, count in sorted(val2_counts.items()):
                        if val2 not in var2_totals:
                            var2_totals[val2] = 0
                        var2_totals[val2] += count
                        
                        rows.append({
                            input.variable1: val1,
                            input.variable2: val2,
                            "count": count,
                            "row_percentage": round(count / row_total * 100, 1) if row_total > 0 else 0,
                            "total_percentage": round(count / total_count * 100, 1) if total_count > 0 else 0,
                        })
                
                results["cross_tabulations"].append({
                    "table": table_name,
                    "actual_var1": var1_match,
                    "actual_var2": var2_match,
                    "total_records": total_count,
                    "var1_categories": len(var1_totals),
                    "var2_categories": len(var2_totals),
                    "rows": rows[:100],  # Limit output size
                    "var1_totals": [{"value": k, "count": v} for k, v in sorted(var1_totals.items())],
                    "var2_totals": [{"value": k, "count": v} for k, v in sorted(var2_totals.items())],
                })
        
        if not results["cross_tabulations"]:
            return {
                "status": "not_found",
                "message": f"Could not find both variables '{input.variable1}' and '{input.variable2}' in the same table",
                "suggestion": "Use search_data_dictionary to find exact variable names",
            }
        
        results["summary"] = {
            "tables_with_both_variables": len(results["cross_tabulations"]),
            "total_cells": sum(len(ct["rows"]) for ct in results["cross_tabulations"]),
        }
        
        return results
        
    except Exception as e:
        logger.error(f"Cross-tabulation failed: {e}")
        return {"error": str(e)}


@mcp.tool()
async def cohort_summary(
    input: CohortSummaryInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Get a comprehensive summary of the RePORT India TB study cohort.
    
    Provides an overview including:
    - Total participants and enrollment
    - Demographics (age, sex distribution)
    - Key comorbidities (HIV, diabetes)
    - Risk factors (smoking, alcohol)
    - Treatment outcomes
    
    SECURITY: Returns ONLY aggregate statistics. NEVER individual records.
    
    Args:
        input: Options for what to include in the summary
        ctx: MCP context
    
    Returns:
        Comprehensive cohort summary with aggregate statistics
    """
    await ctx.info("Generating cohort summary")
    
    try:
        dataset = get_cleaned_dataset()
        
        if not dataset:
            return {"error": "Dataset not available"}
        
        summary = {
            "study": "RePORT India (Indo-VAP) TB Cohort",
            "description": "Multi-site prospective observational cohort studying TB treatment outcomes in India",
            "total_participants": 0,
            "tables_available": list(dataset.keys()),
            "sections": {},
        }
        
        # Try to find enrollment/baseline table
        enrollment_table = None
        enrollment_records = []
        
        for table_name, records in dataset.items():
            if "enrol" in table_name.lower() or "baseline" in table_name.lower():
                enrollment_table = table_name
                enrollment_records = records
                summary["total_participants"] = len(records)
                break
        
        if not enrollment_records:
            # Use any table with the most records
            max_records = 0
            for table_name, records in dataset.items():
                if len(records) > max_records:
                    max_records = len(records)
                    enrollment_table = table_name
                    enrollment_records = records
            summary["total_participants"] = len(enrollment_records)
            summary["note"] = f"Participant count based on {enrollment_table} table"
        
        # Demographics section
        if input.include_demographics and enrollment_records:
            demographics = {}
            sample = enrollment_records[0]
            
            # Age
            age_fields = [k for k in sample.keys() if "age" in k.lower()]
            for field in age_fields[:1]:
                stats = compute_variable_stats(enrollment_records, field)
                if stats.get("type") == "numeric":
                    demographics["age"] = {
                        "field": field,
                        "statistics": stats.get("statistics", {}),
                        "non_null_count": stats.get("non_null_count", 0),
                    }
            
            # Sex
            sex_fields = [k for k in sample.keys() if "sex" in k.lower() or "gender" in k.lower()]
            for field in sex_fields[:1]:
                stats = compute_variable_stats(enrollment_records, field)
                if stats.get("type") == "categorical":
                    demographics["sex"] = {
                        "field": field,
                        "distribution": stats.get("value_counts", []),
                    }
            
            # Site
            site_fields = [k for k in sample.keys() if "site" in k.lower() or "center" in k.lower()]
            for field in site_fields[:1]:
                stats = compute_variable_stats(enrollment_records, field)
                if stats.get("type") == "categorical":
                    demographics["study_site"] = {
                        "field": field,
                        "distribution": stats.get("value_counts", []),
                    }
            
            if demographics:
                summary["sections"]["demographics"] = demographics
        
        # Comorbidities section
        if input.include_comorbidities and enrollment_records:
            comorbidities = {}
            sample = enrollment_records[0]
            
            # HIV
            hiv_fields = [k for k in sample.keys() if "hiv" in k.lower()]
            for field in hiv_fields[:1]:
                stats = compute_variable_stats(enrollment_records, field)
                comorbidities["hiv"] = {
                    "field": field,
                    "distribution": stats.get("value_counts", []) if stats.get("type") == "categorical" else None,
                    "statistics": stats.get("statistics") if stats.get("type") == "numeric" else None,
                }
            
            # Diabetes
            dm_fields = [k for k in sample.keys() if "diab" in k.lower() or "dm" in k.lower() or "glucose" in k.lower()]
            for field in dm_fields[:1]:
                stats = compute_variable_stats(enrollment_records, field)
                comorbidities["diabetes"] = {
                    "field": field,
                    "distribution": stats.get("value_counts", []) if stats.get("type") == "categorical" else None,
                    "statistics": stats.get("statistics") if stats.get("type") == "numeric" else None,
                }
            
            if comorbidities:
                summary["sections"]["comorbidities"] = comorbidities
        
        # Risk factors section
        if input.include_risk_factors and enrollment_records:
            risk_factors = {}
            sample = enrollment_records[0]
            
            # Smoking
            smoke_fields = [k for k in sample.keys() if "smok" in k.lower() or "tobacco" in k.lower()]
            for field in smoke_fields[:1]:
                stats = compute_variable_stats(enrollment_records, field)
                risk_factors["smoking"] = {
                    "field": field,
                    "distribution": stats.get("value_counts", []) if stats.get("type") == "categorical" else None,
                }
            
            # Alcohol
            alcohol_fields = [k for k in sample.keys() if "alco" in k.lower() or "drink" in k.lower()]
            for field in alcohol_fields[:1]:
                stats = compute_variable_stats(enrollment_records, field)
                risk_factors["alcohol"] = {
                    "field": field,
                    "distribution": stats.get("value_counts", []) if stats.get("type") == "categorical" else None,
                }
            
            # BMI
            bmi_fields = [k for k in sample.keys() if "bmi" in k.lower()]
            for field in bmi_fields[:1]:
                stats = compute_variable_stats(enrollment_records, field)
                if stats.get("type") == "numeric":
                    risk_factors["bmi"] = {
                        "field": field,
                        "statistics": stats.get("statistics", {}),
                    }
            
            if risk_factors:
                summary["sections"]["risk_factors"] = risk_factors
        
        # Outcomes section
        if input.include_outcomes:
            outcomes = {}
            
            # Look for outcome table
            for table_name, records in dataset.items():
                if "outcome" in table_name.lower() or "off" in table_name.lower():
                    sample = records[0] if records else {}
                    
                    outcome_fields = [k for k in sample.keys() if "out" in k.lower() or "result" in k.lower()]
                    for field in outcome_fields[:2]:
                        stats = compute_variable_stats(records, field)
                        outcomes[field] = {
                            "table": table_name,
                            "distribution": stats.get("value_counts", []) if stats.get("type") == "categorical" else None,
                            "total_records": stats.get("non_null_count", 0),
                        }
                    break
            
            if outcomes:
                summary["sections"]["treatment_outcomes"] = outcomes
        
        return summary
        
    except Exception as e:
        logger.error(f"Cohort summary failed: {e}")
        return {"error": str(e)}


@mcp.tool()
async def natural_language_query(
    input: NaturalLanguageQueryInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Answer natural language questions about the RePORT India TB study data.
    
    This tool interprets your question, identifies relevant variables,
    and returns comprehensive statistics to answer it.
    
    Example questions:
    - "How many participants have both HIV and diabetes?"
    - "What is the cure rate among smokers vs non-smokers?"
    - "Compare outcomes between males and females"
    - "What percentage of participants are from each study site?"
    - "Is there a relationship between age and TB outcome?"
    
    SECURITY: Returns ONLY aggregate statistics. NEVER individual records.
    
    Args:
        input: Natural language question and options
        ctx: MCP context
    
    Returns:
        Analysis results answering the question with aggregate statistics
    """
    await ctx.info(f"Processing natural language query: {input.question}")
    
    try:
        question_lower = input.question.lower()
        
        # Parse question to identify analysis type and variables
        analysis = {
            "question": input.question,
            "interpretation": {},
            "variables_identified": [],
            "analysis_type": "descriptive",
            "results": {},
        }
        
        # Identify analysis type
        if any(word in question_lower for word in ["compare", "vs", "versus", "between", "difference"]):
            analysis["analysis_type"] = "comparison"
        elif any(word in question_lower for word in ["relationship", "correlation", "association", "related"]):
            analysis["analysis_type"] = "association"
        elif any(word in question_lower for word in ["how many", "count", "number of", "total"]):
            analysis["analysis_type"] = "count"
        elif any(word in question_lower for word in ["percentage", "percent", "proportion", "rate"]):
            analysis["analysis_type"] = "proportion"
        elif any(word in question_lower for word in ["distribution", "breakdown", "spread"]):
            analysis["analysis_type"] = "distribution"
        
        # Identify clinical concepts in the question
        concept_mapping = {
            "hiv": ["hiv", "aids", "human immunodeficiency"],
            "diabetes": ["diabetes", "diabetic", "dm", "glucose", "blood sugar"],
            "smoking": ["smoking", "smoker", "tobacco", "cigarette"],
            "alcohol": ["alcohol", "drinking", "liquor"],
            "age": ["age", "years old", "elderly", "young"],
            "sex": ["sex", "gender", "male", "female", "men", "women"],
            "outcome": ["outcome", "cure", "success", "failure", "death", "result"],
            "site": ["site", "center", "location", "pune", "chennai", "vellore"],
            "bmi": ["bmi", "body mass", "weight", "malnutrition", "underweight"],
            "tb": ["tuberculosis", "tb", "pulmonary"],
        }
        
        identified_concepts = []
        for concept, keywords in concept_mapping.items():
            if any(kw in question_lower for kw in keywords):
                identified_concepts.append(concept)
        
        analysis["interpretation"] = {
            "analysis_type": analysis["analysis_type"],
            "concepts_identified": identified_concepts,
        }
        
        # Use combined_search for each identified concept
        all_statistics = []
        for concept in identified_concepts[:input.max_results]:
            combined_input = CombinedSearchInput(concept=concept, include_statistics=True)
            result = await combined_search(combined_input, ctx)
            
            if result.get("statistics"):
                analysis["variables_identified"].extend([
                    {"concept": concept, "variable": s.get("variable") or s.get("dictionary_field")}
                    for s in result["statistics"]
                ])
                all_statistics.extend(result["statistics"])
        
        analysis["results"]["statistics"] = all_statistics[:input.max_results]
        analysis["results"]["total_variables_analyzed"] = len(all_statistics)
        
        # If comparison analysis, try cross-tabulation
        if analysis["analysis_type"] in ["comparison", "association"] and len(identified_concepts) >= 2:
            cross_input = CrossTabulationInput(
                variable1=identified_concepts[0],
                variable2=identified_concepts[1],
            )
            cross_result = await cross_tabulation(cross_input, ctx)
            if cross_result.get("cross_tabulations"):
                analysis["results"]["cross_tabulation"] = cross_result["cross_tabulations"][0]
        
        # Generate interpretation guidance
        analysis["interpretation"]["guidance"] = (
            f"Based on your question about '{input.question}', I identified these concepts: "
            f"{', '.join(identified_concepts) if identified_concepts else 'none found'}. "
            f"The analysis type appears to be: {analysis['analysis_type']}. "
            f"Review the statistics above to answer your question."
        )
        
        if not all_statistics:
            analysis["interpretation"]["note"] = (
                "No statistics could be computed. Try rephrasing your question or "
                "use search_data_dictionary to find available variables."
            )
        
        return analysis
        
    except Exception as e:
        logger.error(f"Natural language query failed: {e}")
        return {"error": str(e), "question": input.question}


@mcp.tool()
async def variable_details(
    input: VariableDetailsInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Get comprehensive details about a specific variable.
    
    Returns:
    - Data dictionary definition (description, type, module)
    - Codelist values if categorical
    - Aggregate statistics from dataset
    - Data quality metrics (missing %, unique values)
    
    Use this after finding a variable with search_data_dictionary.
    
    SECURITY: Returns ONLY aggregate statistics. NEVER individual records.
    
    Args:
        input: Variable name and options
        ctx: MCP context
    
    Returns:
        Comprehensive variable details including definition and statistics
    """
    await ctx.info(f"Getting details for variable: {input.variable_name}")
    
    try:
        data_dict = get_data_dictionary()
        codelists = get_codelists()
        cleaned_dataset = get_cleaned_dataset()
        
        var_lower = input.variable_name.lower()
        
        result = {
            "variable_name": input.variable_name,
            "definition": None,
            "codelist": None,
            "statistics": None,
            "data_quality": None,
        }
        
        # Search data dictionary for definition
        for table_name, records in data_dict.items():
            for record in records:
                field_name = record.get("Question Short Name (Databank Fieldname)", "")
                if field_name and field_name.lower() == var_lower:
                    result["definition"] = {
                        "field_name": field_name,
                        "description": record.get("Question"),
                        "type": record.get("Type"),
                        "table": record.get("__table__", table_name),
                        "module": record.get("Module"),
                        "form": record.get("Form"),
                        "codelist_ref": record.get("Code List or format"),
                        "notes": record.get("Notes"),
                    }
                    
                    # Get codelist if applicable
                    if input.include_codelist:
                        codelist_ref = record.get("Code List or format", "")
                        if codelist_ref:
                            for cl_name, cl_values in codelists.items():
                                if codelist_ref.lower() in cl_name.lower():
                                    result["codelist"] = {
                                        "name": cl_name,
                                        "values": [
                                            {"code": v.get("Codes"), "description": v.get("Descriptors")}
                                            for v in cl_values
                                        ],
                                    }
                                    break
                    break
            if result["definition"]:
                break
        
        # Get statistics from dataset
        if input.include_statistics:
            for table_name, records in cleaned_dataset.items():
                if not records:
                    continue
                
                sample = records[0]
                
                # Find matching field (exact or partial)
                matched_field = None
                for key in sample.keys():
                    if key.lower() == var_lower or var_lower in key.lower():
                        matched_field = key
                        break
                
                if matched_field:
                    stats = compute_variable_stats(records, matched_field)
                    stats["source_table"] = table_name
                    stats["actual_field_name"] = matched_field
                    result["statistics"] = stats
                    
                    # Compute data quality metrics
                    values = [r.get(matched_field) for r in records]
                    non_null = [v for v in values if v is not None]
                    unique_vals = set(str(v) for v in non_null)
                    
                    result["data_quality"] = {
                        "total_records": len(records),
                        "non_null_count": len(non_null),
                        "null_count": len(values) - len(non_null),
                        "missing_percentage": round((len(values) - len(non_null)) / len(values) * 100, 2),
                        "unique_values": len(unique_vals),
                        "completeness_rating": "Good" if (len(non_null) / len(values)) > 0.9 else "Fair" if (len(non_null) / len(values)) > 0.7 else "Poor",
                    }
                    break
        
        if not result["definition"] and not result["statistics"]:
            return {
                "status": "not_found",
                "variable_name": input.variable_name,
                "suggestion": "Use search_data_dictionary to find exact variable names",
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Variable details failed: {e}")
        return {"error": str(e), "variable_name": input.variable_name}


@mcp.tool()
async def data_quality_report(
    input: DataQualityReportInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Generate a data quality report showing missing data and completeness.
    
    Analyzes:
    - Missing value percentages for each variable
    - Variables with high missing rates (above threshold)
    - Overall dataset completeness
    - Recommendations for analysis
    
    SECURITY: Returns ONLY aggregate quality metrics. NEVER individual records.
    
    Args:
        input: Table filter and threshold options
        ctx: MCP context
    
    Returns:
        Data quality report with missing data analysis
    """
    await ctx.info("Generating data quality report")
    
    try:
        dataset = get_cleaned_dataset()
        
        if not dataset:
            return {"error": "Dataset not available"}
        
        report = {
            "report_type": "data_quality",
            "tables_analyzed": [],
            "overall_metrics": {
                "total_tables": 0,
                "total_variables": 0,
                "total_records": 0,
                "variables_with_issues": 0,
            },
            "table_reports": [],
            "flagged_variables": [],
        }
        
        for table_name, records in dataset.items():
            if input.table_filter and input.table_filter.lower() not in table_name.lower():
                continue
            
            if not records:
                continue
            
            report["tables_analyzed"].append(table_name)
            report["overall_metrics"]["total_tables"] += 1
            report["overall_metrics"]["total_records"] += len(records)
            
            sample = records[0]
            variables_to_check = list(sample.keys())
            
            if input.variables:
                variables_to_check = [v for v in variables_to_check 
                                     if any(iv.lower() in v.lower() for iv in input.variables)]
            
            table_report = {
                "table": table_name,
                "total_records": len(records),
                "total_variables": len(variables_to_check),
                "variable_quality": [],
            }
            
            for var in variables_to_check:
                report["overall_metrics"]["total_variables"] += 1
                
                values = [r.get(var) for r in records]
                non_null = [v for v in values if v is not None and str(v).strip() != ""]
                missing_pct = round((len(values) - len(non_null)) / len(values) * 100, 2)
                
                var_quality = {
                    "variable": var,
                    "non_null_count": len(non_null),
                    "missing_count": len(values) - len(non_null),
                    "missing_percentage": missing_pct,
                    "status": "OK" if missing_pct <= input.threshold_missing else "FLAGGED",
                }
                
                table_report["variable_quality"].append(var_quality)
                
                if missing_pct > input.threshold_missing:
                    report["overall_metrics"]["variables_with_issues"] += 1
                    report["flagged_variables"].append({
                        "table": table_name,
                        "variable": var,
                        "missing_percentage": missing_pct,
                    })
            
            # Sort by missing percentage descending
            table_report["variable_quality"].sort(key=lambda x: x["missing_percentage"], reverse=True)
            table_report["variable_quality"] = table_report["variable_quality"][:30]  # Limit output
            
            report["table_reports"].append(table_report)
        
        # Sort flagged variables
        report["flagged_variables"].sort(key=lambda x: x["missing_percentage"], reverse=True)
        report["flagged_variables"] = report["flagged_variables"][:50]
        
        # Add recommendations
        if report["flagged_variables"]:
            report["recommendations"] = [
                f"Consider data imputation or exclusion criteria for {len(report['flagged_variables'])} variables with >{input.threshold_missing}% missing",
                "Review flagged variables before including in analysis",
                "Document missing data handling in analysis plan",
            ]
        else:
            report["recommendations"] = [
                "Data quality is good - all variables below missing threshold",
                "Proceed with planned analysis",
            ]
        
        return report
        
    except Exception as e:
        logger.error(f"Data quality report failed: {e}")
        return {"error": str(e)}


@mcp.tool()
async def multi_variable_comparison(
    input: MultiVariableComparisonInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Compare statistics across multiple variables side-by-side.
    
    Useful for:
    - Comparing multiple continuous variables (age, BMI, CD4)
    - Comparing distributions of categorical variables
    - Quick overview of related variables
    
    SECURITY: Returns ONLY aggregate statistics. NEVER individual records.
    
    Args:
        input: List of variables to compare
        ctx: MCP context
    
    Returns:
        Side-by-side comparison of variable statistics
    """
    await ctx.info(f"Comparing variables: {', '.join(input.variables)}")
    
    try:
        dataset = get_cleaned_dataset()
        
        if not dataset:
            return {"error": "Dataset not available"}
        
        comparison = {
            "variables_requested": input.variables,
            "variables_found": [],
            "comparison_table": [],
            "summary": {},
        }
        
        for var_name in input.variables:
            var_lower = var_name.lower()
            var_found = False
            
            for table_name, records in dataset.items():
                if input.table_filter and input.table_filter.lower() not in table_name.lower():
                    continue
                
                if not records:
                    continue
                
                sample = records[0]
                
                # Find matching field
                for key in sample.keys():
                    if var_lower in key.lower():
                        stats = compute_variable_stats(records, key)
                        
                        comparison_entry = {
                            "requested_name": var_name,
                            "actual_name": key,
                            "table": table_name,
                            "type": stats.get("type"),
                            "total_records": stats.get("total_records"),
                            "non_null_count": stats.get("non_null_count"),
                            "missing_percentage": stats.get("null_percentage"),
                        }
                        
                        if stats.get("type") == "numeric":
                            comparison_entry["mean"] = stats.get("statistics", {}).get("mean")
                            comparison_entry["median"] = stats.get("statistics", {}).get("median")
                            comparison_entry["min"] = stats.get("statistics", {}).get("min")
                            comparison_entry["max"] = stats.get("statistics", {}).get("max")
                            comparison_entry["std_dev"] = stats.get("statistics", {}).get("std_dev")
                        elif stats.get("type") == "categorical":
                            comparison_entry["unique_values"] = stats.get("unique_values")
                            comparison_entry["top_values"] = stats.get("value_counts", [])[:5]
                        
                        comparison["comparison_table"].append(comparison_entry)
                        comparison["variables_found"].append(var_name)
                        var_found = True
                        break
                
                if var_found:
                    break
        
        # Generate summary
        numeric_vars = [c for c in comparison["comparison_table"] if c.get("type") == "numeric"]
        categorical_vars = [c for c in comparison["comparison_table"] if c.get("type") == "categorical"]
        
        comparison["summary"] = {
            "variables_requested": len(input.variables),
            "variables_found": len(comparison["variables_found"]),
            "variables_not_found": [v for v in input.variables if v not in comparison["variables_found"]],
            "numeric_variables": len(numeric_vars),
            "categorical_variables": len(categorical_vars),
        }
        
        if comparison["summary"]["variables_not_found"]:
            comparison["suggestion"] = (
                f"Variables not found: {', '.join(comparison['summary']['variables_not_found'])}. "
                "Use search_data_dictionary to find exact variable names."
            )
        
        return comparison
        
    except Exception as e:
        logger.error(f"Multi-variable comparison failed: {e}")
        return {"error": str(e)}


# =============================================================================
# MCP Resources
# =============================================================================

@mcp.resource("dictionary://overview")
def get_study_overview() -> str:
    """Overview of the RePORT India study data."""
    data_dict = get_data_dictionary()
    codelists = get_codelists()
    cleaned = get_cleaned_dataset()
    original = get_original_dataset()
    
    dict_fields = sum(len(r) for r in data_dict.values())
    cleaned_records = sum(len(r) for r in cleaned.values())
    original_records = sum(len(r) for r in original.values())
    
    return f"""RePORT India (Indo-VAP) Study Overview

Data Dictionary:
- Tables defined: {len(data_dict)}
- Total fields: {dict_fields}
- Codelists: {len(codelists)}

Cleaned Dataset:
- Tables: {len(cleaned)}
- Total records: {cleaned_records}

Original Dataset:
- Tables: {len(original)}
- Total records: {original_records}

TOOL SELECTION GUIDE:
- For ANY analytical question → Use combined_search (searches ALL data sources)
- For "what variables exist?" or "what does X mean?" ONLY → Use search_data_dictionary

Available Tools (10):
1. combined_search - DEFAULT: Searches ALL data sources for statistics [USE THIS FIRST]
2. natural_language_query - Answer complex multi-concept questions
3. cohort_summary - Comprehensive participant summary (Table 1 style)
4. cross_tabulation - Analyze relationships between two variables
5. variable_details - Deep dive into ONE specific variable
6. data_quality_report - Missing data and completeness analysis
7. multi_variable_comparison - Side-by-side statistics for multiple variables
8. search_data_dictionary - Variable definitions ONLY (no statistics)
9. search_cleaned_dataset - Direct query to cleaned data (when variable known)
10. search_original_dataset - Direct query to original data (fallback)

Available Resources (6):
- dictionary://overview - This overview
- dictionary://tables - List all tables
- dictionary://codelists - All codelist definitions
- dictionary://table/{{name}} - Specific table schema
- dictionary://codelist/{{name}} - Specific codelist values
- study://variables/{{category}} - Variables by category

Available Prompts (4):
- research_question_template - Research question guidance
- data_exploration_guide - Data exploration steps
- statistical_analysis_template - Statistical analysis patterns
- tb_outcome_analysis - TB outcome specific guidance

Security: All tools return aggregates only. Individual records are never exposed.
"""


@mcp.resource("dictionary://tables")
def list_tables() -> str:
    """List all available tables."""
    data_dict = get_data_dictionary()
    cleaned = get_cleaned_dataset()
    
    output = ["Data Dictionary Tables:"]
    for name, records in sorted(data_dict.items()):
        output.append(f"  - {name}: {len(records)} fields")
    
    output.append("\nCleaned Dataset Tables:")
    for name, records in sorted(cleaned.items()):
        output.append(f"  - {name}: {len(records)} records")
    
    return "\n".join(output)


@mcp.resource("dictionary://codelists")
def list_codelists() -> str:
    """List all available codelists with their values."""
    codelists = get_codelists()
    
    output = ["Available Codelists:\n"]
    for name, values in sorted(codelists.items()):
        output.append(f"## {name}")
        for v in values[:10]:  # Limit to first 10 values
            code = v.get("Codes", "")
            desc = v.get("Descriptors", "")
            output.append(f"  {code}: {desc}")
        if len(values) > 10:
            output.append(f"  ... and {len(values) - 10} more values")
        output.append("")
    
    return "\n".join(output)


@mcp.resource("dictionary://table/{table_name}")
def get_table_schema(table_name: str) -> str:
    """Get schema/field definitions for a specific table."""
    data_dict = get_data_dictionary()
    
    # Find matching table (case-insensitive)
    matched_table = None
    for name in data_dict.keys():
        if table_name.lower() in name.lower():
            matched_table = name
            break
    
    if not matched_table:
        return f"Table '{table_name}' not found. Use dictionary://tables to see available tables."
    
    records = data_dict[matched_table]
    
    output = [f"# Table: {matched_table}\n"]
    output.append(f"Total fields: {len(records)}\n")
    output.append("## Fields:\n")
    
    for record in records:
        field_name = record.get("Question Short Name (Databank Fieldname)", "Unknown")
        description = record.get("Question", "No description")
        field_type = record.get("Type", "Unknown")
        codelist = record.get("Code List or format", "")
        
        output.append(f"### {field_name}")
        output.append(f"- Description: {description}")
        output.append(f"- Type: {field_type}")
        if codelist:
            output.append(f"- Codelist/Format: {codelist}")
        output.append("")
    
    return "\n".join(output)


@mcp.resource("dictionary://codelist/{codelist_name}")
def get_codelist_values(codelist_name: str) -> str:
    """Get values for a specific codelist."""
    codelists = get_codelists()
    
    # Find matching codelist (case-insensitive)
    matched_codelist = None
    for name in codelists.keys():
        if codelist_name.lower() in name.lower():
            matched_codelist = name
            break
    
    if not matched_codelist:
        return f"Codelist '{codelist_name}' not found. Use dictionary://codelists to see available codelists."
    
    values = codelists[matched_codelist]
    
    output = [f"# Codelist: {matched_codelist}\n"]
    output.append(f"Total values: {len(values)}\n")
    output.append("| Code | Description |")
    output.append("|------|-------------|")
    
    for v in values:
        code = v.get("Codes", "")
        desc = v.get("Descriptors", "")
        output.append(f"| {code} | {desc} |")
    
    return "\n".join(output)


@mcp.resource("study://variables/{category}")
def get_variables_by_category(category: str) -> str:
    """Get variables organized by clinical category."""
    data_dict = get_data_dictionary()
    
    # Category mappings
    category_keywords = {
        "demographics": ["age", "sex", "gender", "site", "birth", "enrol"],
        "comorbidities": ["hiv", "diab", "dm", "glucose", "hba1c"],
        "risk_factors": ["smok", "tobacco", "alcohol", "drink", "bmi", "weight", "height"],
        "tb_diagnosis": ["tb", "sputum", "smear", "culture", "xpert", "xray", "cxr"],
        "treatment": ["treat", "regimen", "med", "drug", "dose"],
        "outcomes": ["outcome", "cure", "fail", "death", "ltfu", "off"],
        "laboratory": ["lab", "blood", "test", "cd4", "hemo", "creat"],
        "symptoms": ["symptom", "cough", "fever", "sweat", "weight loss"],
    }
    
    category_lower = category.lower()
    keywords = category_keywords.get(category_lower, [category_lower])
    
    output = [f"# Variables related to: {category}\n"]
    
    found_vars = []
    for table_name, records in data_dict.items():
        for record in records:
            field_name = record.get("Question Short Name (Databank Fieldname)", "")
            description = record.get("Question", "")
            searchable = f"{field_name} {description}".lower()
            
            if any(kw in searchable for kw in keywords):
                found_vars.append({
                    "table": table_name,
                    "field": field_name,
                    "description": description,
                    "type": record.get("Type", ""),
                })
    
    if not found_vars:
        output.append(f"No variables found for category '{category}'.\n")
        output.append("Available categories: " + ", ".join(category_keywords.keys()))
    else:
        output.append(f"Found {len(found_vars)} variables:\n")
        for var in found_vars[:50]:  # Limit output
            output.append(f"- **{var['field']}** ({var['table']})")
            output.append(f"  {var['description']}")
    
    return "\n".join(output)


# =============================================================================
# MCP Prompts
# =============================================================================

@mcp.prompt()
def research_question_template() -> str:
    """Template prompt for answering research questions about the TB cohort."""
    return """You are analyzing the RePORT India TB cohort study data through a secure MCP server.

## Study Background
RePORT India (Indo-VAP) is a multi-site prospective observational cohort studying:
- TB treatment outcomes (cure, failure, death, loss to follow-up)
- Comorbidities (HIV, diabetes mellitus)
- Risk factors (smoking, alcohol, malnutrition/BMI)
- Demographics across multiple sites in India

## How to Answer Questions

1. **First**, use `combined_search` with the relevant clinical concept
   - Example: combined_search(concept="HIV status")
   
2. **Interpret** the aggregate statistics returned
   - Note sample sizes and percentages
   - Consider missing data rates
   
3. **For comparisons**, use `cross_tabulation`
   - Example: cross_tabulation(variable1="HIV", variable2="outcome")

4. **For quick overview**, use `cohort_summary`

## Important Guidelines
- Only discuss aggregate statistics (counts, percentages, means)
- Never attempt to identify or discuss individual participants
- Acknowledge limitations (missing data, study design)
- Use exact variable names when querying specific fields

## Example Workflow
Question: "What is the HIV prevalence in the cohort?"
1. Use combined_search(concept="HIV")
2. Find the HIV status variable and its distribution
3. Report: "X% of participants were HIV-positive (N=Y out of Z)"
"""


@mcp.prompt()
def data_exploration_guide() -> str:
    """Guide for exploring the available data."""
    return """# Data Exploration Guide for RePORT India Study

## Step 1: Understand Available Data
- Use resource `dictionary://overview` for study summary
- Use resource `dictionary://tables` for available tables
- Use resource `dictionary://codelists` for categorical value definitions

## Step 2: Find Variables
- Use `search_data_dictionary(query="your term")` to find fields
- Common searches: "HIV", "diabetes", "smoking", "outcome", "age", "BMI"

## Step 3: Get Statistics
- Use `combined_search(concept="topic")` for automatic analysis
- Use `search_cleaned_dataset(variable="exact_name")` for specific fields

## Step 4: Analyze Relationships
- Use `cross_tabulation(variable1="A", variable2="B")` for associations
- Example: HIV status vs treatment outcome

## Step 5: Get Cohort Overview
- Use `cohort_summary()` for comprehensive participant summary

## Tips
- Variable names are often abbreviated (e.g., "SMOKHX" for smoking history)
- Check codelists to understand categorical values
- Start broad with combined_search, then narrow down
"""


@mcp.prompt()
def statistical_analysis_template() -> str:
    """Template for conducting statistical analyses."""
    return """# Statistical Analysis Template

## Descriptive Statistics
1. **Demographics**: Use cohort_summary() or combined_search("demographics")
2. **Continuous variables**: Look for mean, median, std_dev, min, max
3. **Categorical variables**: Look for value_counts with percentages

## Bivariate Analysis
1. **Cross-tabulations**: Use cross_tabulation(var1, var2)
2. **Interpretation**: 
   - Row percentages show distribution of var2 within var1 categories
   - Total percentages show overall distribution

## Common Analysis Patterns

### Prevalence calculation
```
combined_search(concept="HIV")
# Look at categorical distribution
# Prevalence = count of positive / total non-null
```

### Risk factor association
```
cross_tabulation(variable1="smoking", variable2="outcome")
# Compare outcome percentages across smoking categories
```

### Cohort characteristics table
```
cohort_summary(include_demographics=True, include_comorbidities=True)
# Generates Table 1 style summary
```

## Limitations to Acknowledge
- This is aggregate data only
- Cannot perform multivariate analysis
- Cannot assess statistical significance directly
- Missing data may affect estimates
"""


@mcp.prompt()
def tb_outcome_analysis() -> str:
    """Specific prompt for TB treatment outcome analysis."""
    return """# TB Treatment Outcome Analysis Guide

## Understanding TB Outcomes
The WHO-defined TB treatment outcomes include:
- **Cured**: Culture/smear negative at treatment completion
- **Treatment Completed**: Completed treatment without bacteriological confirmation
- **Treatment Failure**: Positive culture/smear at month 5 or later
- **Died**: Death from any cause during treatment
- **Lost to Follow-up (LTFU)**: Treatment interrupted for ≥2 months
- **Not Evaluated**: No outcome assigned

## Analysis Steps

### 1. Get outcome distribution
```
combined_search(concept="treatment outcome")
```

### 2. Analyze by risk factors
```
cross_tabulation(variable1="HIV", variable2="outcome")
cross_tabulation(variable1="diabetes", variable2="outcome")
cross_tabulation(variable1="smoking", variable2="outcome")
```

### 3. Demographic patterns
```
cross_tabulation(variable1="sex", variable2="outcome")
cross_tabulation(variable1="site", variable2="outcome")
```

### 4. Key outcome variables to look for:
- OUTCLIN: Clinical outcome
- OUTOTH: Other outcome classification
- TB_OUTCOME: Combined outcome
- Look in 'outcome' or 'offstudy' tables

## Reporting Results
- Report sample sizes with percentages
- Compare favorable (cure + completed) vs unfavorable outcomes
- Note differences across subgroups
"""


# =============================================================================
# Tool Registry
# =============================================================================

def get_tool_registry() -> dict[str, Any]:
    """Get summary of registered tools, resources, and prompts."""
    data_dict = get_data_dictionary()
    codelists = get_codelists()
    cleaned = get_cleaned_dataset()
    original = get_original_dataset()
    
    return {
        "server_name": SERVER_NAME,
        "version": SERVER_VERSION,
        "registered_tools": [
            # Core search tools
            "search_data_dictionary",
            "search_cleaned_dataset", 
            "search_original_dataset",
            "combined_search",
            # Enhanced analysis tools
            "cross_tabulation",
            "cohort_summary",
            "natural_language_query",
            # Detailed analysis tools
            "variable_details",
            "data_quality_report",
            "multi_variable_comparison",
        ],
        "registered_resources": [
            # Overview resources
            "dictionary://overview",
            "dictionary://tables",
            "dictionary://codelists",
            # Dynamic resources
            "dictionary://table/{table_name}",
            "dictionary://codelist/{codelist_name}",
            "study://variables/{category}",
        ],
        "registered_prompts": [
            "research_question_template",
            "data_exploration_guide",
            "statistical_analysis_template",
            "tb_outcome_analysis",
        ],
        "data_loaded": {
            "dictionary_tables": len(data_dict),
            "dictionary_fields": sum(len(r) for r in data_dict.values()),
            "codelists": len(codelists),
            "cleaned_tables": len(cleaned),
            "cleaned_records": sum(len(r) for r in cleaned.values()),
            "original_tables": len(original),
            "original_records": sum(len(r) for r in original.values()),
        },
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": True,
            "subscriptions": False,
        },
    }
