"""
MCP Tool Definitions for RePORTaLiN.

This module implements 4 secure tools for clinical data analysis:

1. search_data_dictionary - Search variable definitions, codelists, metadata
2. search_cleaned_dataset - Query de-identified cleaned data (aggregates only)
3. search_original_dataset - Query de-identified original data (aggregates only)
4. combined_search - Cross-reference dictionary with dataset for accurate answers

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

## PRIMARY TOOL - Use for ALL Questions

**combined_search** - The main tool for answering ANY question about the data
- Automatically searches data dictionary to find relevant variables
- Retrieves aggregate statistics from cleaned dataset
- Falls back to original dataset if needed
- Handles clinical concepts, research questions, and data exploration

USE combined_search FOR:
- "How many participants have diabetes?"
- "What is the age distribution?"
- "Show me smoking-related variables"
- "What are the treatment outcomes?"
- "HIV status in the cohort"
- "BMI and malnutrition data"
- ANY general question about the study

## Supporting Tools (for specific needs)

1. **search_data_dictionary** - Find variable definitions only
   - Use when you ONLY need metadata, not statistics
   
2. **search_cleaned_dataset** - Query specific known variables
   - Use when you already know exact variable names
   
3. **search_original_dataset** - Query original data
   - Use only if cleaned data is missing something

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
    """Load all data dictionary JSONL files."""
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
    """Load all codelist definitions."""
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
    """Load dataset from a directory of JSONL files."""
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
    """Get cached data dictionary."""
    global _dict_cache
    if _dict_cache is None:
        _dict_cache = load_data_dictionary()
    return _dict_cache


def get_codelists() -> dict[str, list[dict]]:
    """Get cached codelists."""
    global _codelist_cache
    if _codelist_cache is None:
        _codelist_cache = load_codelists()
    return _codelist_cache


def get_cleaned_dataset() -> dict[str, list[dict]]:
    """Get cached cleaned dataset."""
    global _cleaned_cache
    if _cleaned_cache is None:
        _cleaned_cache = load_dataset(CLEANED_DATA_PATH)
    return _cleaned_cache


def get_original_dataset() -> dict[str, list[dict]]:
    """Get cached original dataset."""
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
    """Compute histogram bins for numeric data."""
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
    """Find which tables contain a variable."""
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


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
async def search_data_dictionary(
    input: DictionarySearchInput,
    ctx: Context,
) -> dict[str, Any]:
    """
    Search the data dictionary for variable definitions and codelists.
    
    Use this tool FIRST to find:
    - Exact variable/field names in the database
    - Variable descriptions and data types
    - Valid codes for categorical variables
    - Which tables contain specific variables
    
    This is SAFE to use - returns metadata, not patient data.
    
    Args:
        input: Search parameters
        ctx: MCP context
    
    Returns:
        Matching variables and codelists from the data dictionary
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
    
    This is the main tool for all queries. It:
    1. Parses your question/concept into search terms
    2. Searches the DATA DICTIONARY to find relevant variables (not guessing)
    3. Searches the CLEANED DATASET for aggregate statistics
    4. Falls back to ORIGINAL DATASET if cleaned doesn't have the data
    5. Returns codelist values for categorical variables
    
    Use this for questions like:
    - "How many participants have diabetes?"
    - "What is the smoking status distribution?"
    - "Show me HIV-related variables and statistics"
    - "What are the treatment outcomes?"
    - "Age and sex distribution"
    - "BMI/malnutrition data"
    
    SECURITY: Returns ONLY aggregate statistics. NEVER individual records.
    
    Args:
        input: Clinical concept, research question, or variable name to analyze
        ctx: MCP context
    
    Returns:
        Variables found in dictionary + aggregate statistics from dataset
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

Available Tools:
1. search_data_dictionary - Find variable names and definitions
2. search_cleaned_dataset - Get statistics from cleaned data
3. search_original_dataset - Get statistics from original data
4. combined_search - Full analysis (dictionary + statistics)

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


# =============================================================================
# Tool Registry
# =============================================================================

def get_tool_registry() -> dict[str, Any]:
    """Get summary of registered tools."""
    data_dict = get_data_dictionary()
    codelists = get_codelists()
    cleaned = get_cleaned_dataset()
    original = get_original_dataset()
    
    return {
        "server_name": SERVER_NAME,
        "version": SERVER_VERSION,
        "registered_tools": [
            "search_data_dictionary",
            "search_cleaned_dataset", 
            "search_original_dataset",
            "combined_search",
        ],
        "registered_resources": [
            "dictionary://overview",
            "dictionary://tables",
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
    }
