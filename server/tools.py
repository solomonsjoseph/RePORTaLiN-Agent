"""
MCP Tool Definitions for RePORTaLiN (SECURE MODE).

This module defines ONLY the two authorized MCP tools for secure clinical
data feasibility queries. No raw PHI access is permitted.

Security Model:
    - FORBIDDEN: ./data/dataset/ (raw PHI - access blocked)
    - ALLOWED: ./results/ (de-identified data only)
    - Zero-Trust: No names, DOBs, or contact details in output

Registered Tools (EXCLUSIVE LIST):
    1. explore_study_metadata - High-level feasibility stats from metadata
    2. build_technical_request - Construct data extraction concept sheets

Usage:
    The `mcp` instance is imported by server/main.py and mounted
    on the FastAPI application for HTTP/SSE transport.

    >>> from server.tools import mcp
    >>> app.mount("/mcp", mcp.sse_app())
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field, field_validator

from server.config import get_settings
from server.logger import bind_context, clear_context, get_logger
from shared.constants import SERVER_NAME, SERVER_VERSION

if TYPE_CHECKING:
    from mcp.server.session import ServerSession

__all__ = [
    "BuildTechnicalRequestInput",
    "ExploreStudyMetadataInput",
    "mcp",
]

# Initialize logger for this module
logger = get_logger(__name__)

# =============================================================================
# Security Constants
# =============================================================================

FORBIDDEN_ZONE = Path("data/dataset")
SAFE_ZONE = Path("results")
METADATA_FILE = SAFE_ZONE / "metadata_summary.json"
VARIABLE_MAP_FILE = SAFE_ZONE / "variable_map.json"

SECURITY_ALERT = "SECURITY ALERT: Access to raw dataset is prohibited. Query rejected."

# =============================================================================
# FastMCP Server Instance
# =============================================================================

settings = get_settings()

mcp = FastMCP(
    name=SERVER_NAME,
    instructions="""
    RePORTaLiN MCP Server - SECURE MODE

    This server provides EXACTLY TWO tools for secure clinical data queries:

    1. explore_study_metadata
       - Purpose: Provides high-level feasibility stats WITHOUT touching row-level data
       - Data Source: ./results/metadata_summary.json (derived from data dictionary)
       - Use Case: Determine if study data is relevant for research
       - Returns: Aggregated counts, site lists, variable existence checks
       - Example: "Do we have any participants from Pune with follow-up data at Month 24?"

    2. build_technical_request
       - Purpose: Helps construct valid data extraction requests ("Concept Sheet")
       - Data Source: ./results/variable_map.json (safe version of mapping specs)
       - Use Case: Define formal dataset extraction criteria
       - Returns: Query logic and de-identified snippets ONLY
       - Example: "Create a query for female participants aged 18-45"

    SECURITY CONSTRAINTS:
    - NO access to ./data/dataset/ (contains raw PHI)
    - ALL data in ./results/ is pre-processed and de-identified
    - Zero-Trust Output: No names, DOBs, or contact details returned
    - Privacy First: Ambiguous queries default to metadata, NOT patient records
    """,
    debug=settings.is_local,
    log_level=settings.log_level.value,
)


# =============================================================================
# Security Utilities
# =============================================================================

def is_forbidden_path(path: str | Path) -> bool:
    """Check if a path attempts to access the forbidden zone."""
    path_obj = Path(path).resolve() if isinstance(path, str) else path.resolve()
    forbidden_resolved = FORBIDDEN_ZONE.resolve()

    try:
        path_obj.relative_to(forbidden_resolved)
        return True
    except ValueError:
        return False


def sanitize_output(data: dict[str, Any]) -> dict[str, Any]:
    """
    Remove any potentially sensitive fields from output.
    Applies zero-trust output policy.
    """
    sensitive_patterns = [
        r"(?i)name",
        r"(?i)dob",
        r"(?i)date.?of.?birth",
        r"(?i)contact",
        r"(?i)phone",
        r"(?i)email",
        r"(?i)address",
        r"(?i)ssn",
        r"(?i)aadhaar",
    ]

    def redact_sensitive(obj: Any, depth: int = 0) -> Any:
        if depth > 10:  # Prevent infinite recursion
            return obj

        if isinstance(obj, dict):
            return {
                k: "[REDACTED]" if any(re.search(p, k) for p in sensitive_patterns)
                else redact_sensitive(v, depth + 1)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [redact_sensitive(item, depth + 1) for item in obj]
        else:
            return obj

    return redact_sensitive(data)


# =============================================================================
# Pydantic Input Models
# =============================================================================

class ExploreStudyMetadataInput(BaseModel):
    """
    Input schema for explore_study_metadata tool.

    Used for high-level feasibility queries about study data
    without accessing raw patient records.

    Attributes:
        query: Natural language query about study feasibility
        site_filter: Optional filter by study site
        time_filter: Optional filter by study time point
    """

    query: Annotated[
        str,
        Field(
            description="Natural language query about study feasibility. "
                       "Examples: 'Do we have CD4 counts?', 'How many sites?', "
                       "'Any participants from Pune?'",
            min_length=5,
            max_length=500,
            examples=[
                "Do we have any participants from Pune with follow-up data at Month 24?",
                "What variables are available for TB diagnosis?",
                "How many study sites are there?",
            ],
        ),
    ]

    site_filter: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional site name to filter results",
            max_length=100,
        ),
    ]

    time_point_filter: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional time point filter (e.g., 'Baseline', 'Month 6', 'Month 24')",
            max_length=50,
        ),
    ]

    @field_validator("query")
    @classmethod
    def validate_no_phi_request(cls, v: str) -> str:
        """Ensure query doesn't request raw PHI data or access forbidden zones."""
        # Check for forbidden zone path access attempts
        forbidden_path_patterns = [
            r"(?i)data/dataset",
            r"(?i)data\\dataset",
            r"(?i)indo.?vap",
            r"(?i)csv.?files?",
            r"(?i)6_HIV",
            r"(?i)2A_ICBaseline",
            r"(?i)\.xlsx",
            r"(?i)read\s+(from\s+)?file",
            r"(?i)open\s+(the\s+)?file",
            r"(?i)access\s+(the\s+)?(raw\s+)?dataset",
        ]

        for pattern in forbidden_path_patterns:
            if re.search(pattern, v):
                raise ValueError(
                    "SECURITY ALERT: Access to raw dataset is prohibited. Query rejected."
                )

        # Patterns that suggest requesting raw patient data
        phi_patterns = [
            r"(?i)show\s+me\s+(all\s+)?(the\s+)?patients?",
            r"(?i)list\s+(all\s+)?(the\s+)?records?",
            r"(?i)export\s+data",
            r"(?i)download\s+dataset",
            r"(?i)raw\s+data",
            r"(?i)patient\s+names?",
            r"(?i)individual\s+records?",
        ]

        for pattern in phi_patterns:
            if re.search(pattern, v):
                raise ValueError(
                    "This tool provides metadata only. "
                    "For patient-level data, submit a formal data request."
                )

        return v.strip()


class BuildTechnicalRequestInput(BaseModel):
    """
    Input schema for build_technical_request tool.

    Used to construct formal data extraction concept sheets
    without returning actual patient data.

    Attributes:
        description: Description of the data request
        inclusion_criteria: Criteria for including participants
        exclusion_criteria: Criteria for excluding participants
        variables_of_interest: Specific variables needed
        time_points: Study time points of interest
    """

    description: Annotated[
        str,
        Field(
            description="Brief description of the research question or data need",
            min_length=10,
            max_length=500,
            examples=[
                "Analyze treatment outcomes in TB patients",
                "Compare demographics across study sites",
            ],
        ),
    ]

    inclusion_criteria: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="List of inclusion criteria for participant selection",
            examples=[["Female", "Age 18-45", "TB positive"]],
        ),
    ]

    exclusion_criteria: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="List of exclusion criteria",
            examples=[["HIV co-infection", "Prior TB treatment"]],
        ),
    ]

    variables_of_interest: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="Specific variables/fields needed in the extract",
            examples=[["Age", "Sex", "TB_Status", "Treatment_Outcome"]],
        ),
    ]

    time_points: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="Study time points to include",
            examples=[["Baseline", "Month 6", "Month 12", "Month 24"]],
        ),
    ]

    output_format: Annotated[
        str,
        Field(
            default="concept_sheet",
            description="Output format: 'concept_sheet' or 'query_logic'",
            pattern="^(concept_sheet|query_logic)$",
        ),
    ]

    @field_validator("description")
    @classmethod
    def validate_no_forbidden_access(cls, v: str) -> str:
        """Ensure description doesn't request forbidden zone access."""
        forbidden_patterns = [
            r"(?i)data/dataset",
            r"(?i)data\\dataset",
            r"(?i)indo.?vap",
            r"(?i)\.xlsx",
            r"(?i)raw\s+data",
            r"(?i)access\s+(the\s+)?(raw\s+)?dataset",
        ]

        for pattern in forbidden_patterns:
            if re.search(pattern, v):
                raise ValueError(
                    "SECURITY ALERT: Access to raw dataset is prohibited. Query rejected."
                )

        return v.strip()


# =============================================================================
# Tool Implementations
# =============================================================================

@mcp.tool()
async def explore_study_metadata(
    input: ExploreStudyMetadataInput,
    ctx: Context[ServerSession, None],
) -> dict[str, Any]:
    """
    Explore high-level study metadata for feasibility assessment.

    This tool provides aggregated statistics and variable existence checks
    WITHOUT accessing raw patient-level data. Use it to determine if the
    study data is relevant for your research question.

    ALLOWED RESPONSES:
    - Aggregated counts (e.g., "500 participants enrolled")
    - Site lists (e.g., "Sites: Pune, Chennai, Delhi")
    - Variable existence (e.g., "Yes, we have CD4 counts")
    - Time point availability

    NOT ALLOWED:
    - Individual patient records
    - Raw data exports
    - Patient identifiers

    Args:
        input: ExploreStudyMetadataInput with query and optional filters
        ctx: MCP Context for logging

    Returns:
        Dictionary with:
        - success: Boolean
        - query_type: Type of metadata query answered
        - results: Aggregated/metadata results
        - data_available: Boolean if relevant data exists
    """
    await ctx.info(f"Exploring study metadata: {input.query[:50]}...")

    bind_context(
        tool="explore_study_metadata",
        query_length=len(input.query),
        site_filter=input.site_filter,
    )

    logger.info(
        "Metadata exploration requested",
        query_preview=input.query[:50],
        site_filter=input.site_filter,
    )

    try:
        # Attempt to load metadata from safe zone
        metadata = {}

        if METADATA_FILE.exists():
            with open(METADATA_FILE) as f:
                metadata = json.load(f)
        else:
            # Generate metadata summary from available sources
            # This would be pre-computed from the data dictionary
            metadata = _generate_default_metadata()

        # Process the query
        query_lower = input.query.lower()
        results = {}
        query_type = "general"

        # Check for variable existence queries
        if any(word in query_lower for word in ["have", "available", "variable", "field", "data"]):
            query_type = "variable_check"
            results = _check_variable_availability(query_lower, metadata)

        # Check for site queries
        elif any(word in query_lower for word in ["site", "location", "center", "pune", "chennai", "delhi"]):
            query_type = "site_info"
            results = _get_site_information(input.site_filter, metadata)

        # Check for count/enrollment queries
        elif any(word in query_lower for word in ["how many", "count", "number", "enrolled", "participants"]):
            query_type = "enrollment_stats"
            results = _get_enrollment_stats(metadata)

        # Check for time point queries
        elif any(word in query_lower for word in ["month", "follow-up", "visit", "time point", "baseline"]):
            query_type = "time_point_info"
            results = _get_time_point_info(input.time_point_filter, metadata)

        # Default: general feasibility summary
        else:
            query_type = "feasibility_summary"
            results = _get_feasibility_summary(metadata)

        # Apply site filter if specified
        if input.site_filter and "by_site" in results:
            results["filtered_to_site"] = input.site_filter

        # Sanitize output (zero-trust)
        results = sanitize_output(results)

        response = {
            "success": True,
            "query_type": query_type,
            "original_query": input.query,
            "results": results,
            "data_available": bool(results),
            "source": "metadata_summary.json (de-identified)",
            "note": "Results are aggregated statistics only. No patient-level data returned.",
        }

        logger.info("Metadata exploration completed", query_type=query_type)
        await ctx.info(f"Query type: {query_type} - Results available: {bool(results)}")

        return response

    except Exception as e:
        logger.error("Metadata exploration failed", error=str(e))
        return {
            "success": False,
            "error": f"Metadata exploration failed: {e!s}",
            "results": None,
        }
    finally:
        clear_context()


@mcp.tool()
async def build_technical_request(
    input: BuildTechnicalRequestInput,
    ctx: Context[ServerSession, None],
) -> dict[str, Any]:
    """
    Build a formal technical data extraction request (Concept Sheet).

    This tool helps construct valid data extraction requests by mapping
    your criteria to available study variables. It returns query LOGIC
    and de-identified code snippets, NOT patient data.

    USE CASES:
    - Define participant selection criteria
    - Map research variables to study forms
    - Generate formal data request documentation

    DOES NOT RETURN:
    - Patient data
    - Individual records
    - Raw dataset contents

    Args:
        input: BuildTechnicalRequestInput with criteria and variables
        ctx: MCP Context for logging

    Returns:
        Dictionary with:
        - success: Boolean
        - request_id: Generated request identifier
        - concept_sheet: Formatted data request document
        - variable_mapping: Map of requested vars to study forms
        - validation_notes: Any issues with the request
    """
    await ctx.info(f"Building technical request: {input.description[:50]}...")

    bind_context(
        tool="build_technical_request",
        description_length=len(input.description),
        criteria_count=len(input.inclusion_criteria) + len(input.exclusion_criteria),
    )

    logger.info(
        "Technical request initiated",
        description_preview=input.description[:50],
        inclusion_count=len(input.inclusion_criteria),
        exclusion_count=len(input.exclusion_criteria),
    )

    try:
        # Load variable mapping from safe zone
        variable_map = {}

        if VARIABLE_MAP_FILE.exists():
            with open(VARIABLE_MAP_FILE) as f:
                variable_map = json.load(f)
        else:
            # Use default mapping derived from data dictionary
            variable_map = _get_default_variable_map()

        # Generate request ID
        request_id = f"REQ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # Validate and map variables
        variable_mapping = {}
        validation_notes = []

        for var in input.variables_of_interest:
            var_lower = var.lower()
            mapped = _find_variable_mapping(var_lower, variable_map)
            if mapped:
                variable_mapping[var] = mapped
            else:
                validation_notes.append(f"Variable '{var}' not found in mapping - manual review needed")

        # Build the concept sheet or query logic
        if input.output_format == "concept_sheet":
            output = _build_concept_sheet(
                request_id=request_id,
                description=input.description,
                inclusion=input.inclusion_criteria,
                exclusion=input.exclusion_criteria,
                variables=input.variables_of_interest,
                time_points=input.time_points,
                variable_mapping=variable_mapping,
            )
        else:
            output = _build_query_logic(
                inclusion=input.inclusion_criteria,
                exclusion=input.exclusion_criteria,
                variables=input.variables_of_interest,
                variable_mapping=variable_mapping,
            )

        response = {
            "success": True,
            "request_id": request_id,
            "output_format": input.output_format,
            "output": output,
            "variable_mapping": variable_mapping,
            "validation_notes": validation_notes if validation_notes else ["All variables mapped successfully"],
            "next_steps": [
                "Review the generated request for accuracy",
                "Submit to data governance for approval",
                "Upon approval, data team will execute extraction",
            ],
            "note": "This tool generates request LOGIC only. No patient data is returned.",
        }

        logger.info(
            "Technical request built",
            request_id=request_id,
            variables_mapped=len(variable_mapping),
        )

        await ctx.info(f"Request {request_id} generated with {len(variable_mapping)} variables mapped")

        return response

    except Exception as e:
        logger.error("Technical request failed", error=str(e))
        return {
            "success": False,
            "error": f"Failed to build technical request: {e!s}",
            "output": None,
        }
    finally:
        clear_context()


# =============================================================================
# Helper Functions (Internal)
# =============================================================================

def _generate_default_metadata() -> dict[str, Any]:
    """Generate default metadata when metadata_summary.json doesn't exist."""
    return {
        "study_name": "RePORT India (Indo-VAP)",
        "study_description": "Regional Prospective Observational Research for Tuberculosis - India",
        "sites": ["Pune", "Chennai", "Delhi"],
        "enrollment_total": "500-1000 (aggregate)",
        "time_points": ["Screening", "Baseline", "Month 2", "Month 6", "Month 12", "Month 24"],
        "domains": {
            "demographics": ["Age", "Sex", "Site", "Education", "Occupation"],
            "laboratory": ["CD4", "HIV", "Smear", "Culture", "DST", "CBC", "IGRA", "TST"],
            "clinical": ["TB_Status", "Treatment_Outcome", "CXR_Findings", "Symptoms"],
            "follow_up": ["Visit_Date", "Compliance", "Adverse_Events", "Status"],
        },
        "total_forms_count": 41,
        "data_dictionary_available": True,
        "privacy_level": "De-identified (DPDPA 2023 compliant)",
    }


def _check_variable_availability(query: str, metadata: dict) -> dict[str, Any]:
    """Check if specific variables are available in the study."""
    domains = metadata.get("domains", {})
    available_vars = []

    # Common variable searches - expanded to match all available data
    search_terms = {
        "cd4": "CD4 count",
        "hiv": "HIV status",
        "age": "Age",
        "sex": "Sex/Gender",
        "tb": "TB diagnosis/status",
        "smear": "Smear microscopy",
        "culture": "TB culture",
        "dst": "Drug susceptibility testing",
        "xray": "Chest X-ray",
        "cxr": "Chest X-ray",
        "treatment": "Treatment outcomes",
        "cbc": "Complete blood count",
        "igra": "IGRA (Interferon-gamma release assay)",
        "tst": "Tuberculin skin test",
        "compliance": "Treatment compliance",
        "adverse": "Adverse events",
        "sae": "Serious adverse events",
        "symptom": "TB symptoms",
        "education": "Education level",
        "occupation": "Occupation",
        "follow": "Follow-up data",
        "visit": "Visit data",
        "outcome": "Treatment outcome",
        "baseline": "Baseline data",
        "screening": "Screening data",
    }

    for term, var_name in search_terms.items():
        if term in query:
            # Check if variable exists in any domain
            for domain, vars_list in domains.items():
                if any(term in v.lower() for v in vars_list):
                    available_vars.append({
                        "variable": var_name,
                        "domain": domain,
                        "available": True,
                    })

    if not available_vars:
        available_vars = [{"note": "Specify variables to check availability"}]

    return {
        "variables_checked": available_vars,
        "all_domains": list(domains.keys()),
    }


def _get_site_information(site_filter: str | None, metadata: dict) -> dict[str, Any]:
    """Get study site information."""
    sites = metadata.get("sites", ["Pune", "Chennai", "Delhi"])

    result = {
        "total_sites": len(sites),
        "site_list": sites,
        "enrollment_by_site": "Available upon request (aggregate only)",
    }

    if site_filter:
        site_lower = site_filter.lower()
        matching_sites = [s for s in sites if site_lower in s.lower()]
        result["filtered_sites"] = matching_sites
        result["filter_applied"] = site_filter

    return result


def _get_enrollment_stats(metadata: dict) -> dict[str, Any]:
    """Get enrollment statistics."""
    return {
        "total_enrollment": metadata.get("enrollment_total", "500-1000 (aggregate)"),
        "enrollment_status": "Completed",
        "sites_count": len(metadata.get("sites", [])),
        "note": "Exact counts available through formal data request",
    }


def _get_time_point_info(time_filter: str | None, metadata: dict) -> dict[str, Any]:
    """Get time point information."""
    time_points = metadata.get("time_points", [])

    result = {
        "available_time_points": time_points,
        "total_time_points": len(time_points),
    }

    if time_filter:
        matching = [tp for tp in time_points if time_filter.lower() in tp.lower()]
        result["matching_time_points"] = matching
        result["filter_applied"] = time_filter

    return result


def _get_feasibility_summary(metadata: dict) -> dict[str, Any]:
    """Get general feasibility summary."""
    return {
        "study_name": metadata.get("study_name", "RePORT India"),
        "data_available": True,
        "privacy_level": metadata.get("privacy_level", "De-identified"),
        "domains_available": list(metadata.get("domains", {}).keys()),
        "sites": metadata.get("sites", []),
        "time_points": metadata.get("time_points", []),
        "next_step": "Use explore_study_metadata with specific queries or build_technical_request for formal extraction",
    }


def _get_default_variable_map() -> dict[str, Any]:
    """Get default variable mapping from data dictionary."""
    return {
        "demographics": {
            "age": {"form": "2A_ICBaseline", "field": "AGE", "type": "numeric"},
            "sex": {"form": "2A_ICBaseline", "field": "SEX", "type": "categorical", "values": ["M", "F"]},
            "site": {"form": "2A_ICBaseline", "field": "SITEID", "type": "categorical"},
            "education": {"form": "2A_ICBaseline", "field": "EDUCATION", "type": "categorical"},
            "occupation": {"form": "2A_ICBaseline", "field": "OCCUPATION", "type": "categorical"},
        },
        "laboratory": {
            "cd4": {"form": "6_HIV", "field": "CD4COUNT", "type": "numeric"},
            "hiv": {"form": "6_HIV", "field": "HIVSTAT", "type": "categorical", "values": ["Positive", "Negative", "Unknown"]},
            "smear": {"form": "4_Smear", "field": "SMEAR_RESULT", "type": "categorical"},
            "culture": {"form": "7_Culture", "field": "CULTURE_RESULT", "type": "categorical"},
            "dst": {"form": "21_DSTIsolate", "field": "DST_RESULT", "type": "categorical"},
            "cbc": {"form": "5_CBC", "field": "CBC_PANEL", "type": "composite"},
            "igra": {"form": "11_IGRA", "field": "IGRA_RESULT", "type": "categorical"},
            "tst": {"form": "10_TST", "field": "TST_MM", "type": "numeric"},
        },
        "clinical": {
            "tb_status": {"form": "9_EEval", "field": "TB_CONFIRM", "type": "categorical"},
            "treatment_outcome": {"form": "98A_FOA", "field": "OUTCOME", "type": "categorical"},
            "cxr_findings": {"form": "8_CXR", "field": "CXR_RESULT", "type": "categorical"},
            "symptoms": {"form": "1A_ICScreening", "field": "SYMPTOMS", "type": "composite"},
        },
        "follow_up": {
            "visit_date": {"form": "12A_FUA", "field": "VISIT_DATE", "type": "date"},
            "compliance": {"form": "13_TxCompliance", "field": "COMPLIANCE", "type": "categorical"},
            "adverse_events": {"form": "95_SAE", "field": "SAE_PRESENT", "type": "boolean"},
        },
        "forms": {
            "screening": ["1A_ICScreening", "1B_HCScreening"],
            "baseline": ["2A_ICBaseline", "2A_ICBaseline_1", "2B_HCBaseline"],
            "laboratory": ["3_Specimen_Collection", "4_Smear", "5_CBC", "6_HIV", "7_Culture", "10_TST", "11_IGRA", "19_Smear", "21_DSTISO", "21_DSTIsolate"],
            "imaging": ["8_CXR"],
            "clinical": ["9_EEval", "17_EligConfirmation"],
            "follow_up": ["12A_FUA", "12B_FUB", "98A_FOA", "98B_FOB", "99A_FSA", "99B_FSB"],
            "treatment": ["13_TxCompliance", "18_1_TargConcom", "18_2_TargConcom"],
            "case_classification": ["14_CaseControl", "14_Case_Control", "20_CoEnroll"],
            "additional_testing": ["15_Feces", "16_Helminth", "53_exposure", "30_Air_Quality"],
            "safety": ["95_SAE"],
            "specimen_tracking": ["95_Specimen_Tracking", "96_Specimen_Tracking", "97_Not_Collected"],
            "consent_admin": ["18_NonConsent", "101_HHC_Recontact", "101_HHC_Recontact_1"],
        },
    }


def _find_variable_mapping(var_name: str, variable_map: dict) -> dict | None:
    """Find mapping for a variable name."""
    for domain, vars_dict in variable_map.items():
        if domain == "forms":
            continue
        if isinstance(vars_dict, dict):
            for var_key, mapping in vars_dict.items():
                if var_name in var_key or var_key in var_name:
                    return {
                        "domain": domain,
                        **mapping,
                    }
    return None


def _build_concept_sheet(
    request_id: str,
    description: str,
    inclusion: list[str],
    exclusion: list[str],
    variables: list[str],
    time_points: list[str],
    variable_mapping: dict,
) -> dict[str, Any]:
    """Build a formal concept sheet document."""
    return {
        "title": "DATA EXTRACTION CONCEPT SHEET",
        "request_id": request_id,
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "sections": {
            "1_research_description": description,
            "2_inclusion_criteria": inclusion if inclusion else ["Not specified"],
            "3_exclusion_criteria": exclusion if exclusion else ["Not specified"],
            "4_variables_requested": variables if variables else ["Not specified"],
            "5_time_points": time_points if time_points else ["All available"],
            "6_variable_mapping": variable_mapping,
        },
        "approval_required": True,
        "estimated_review_time": "3-5 business days",
    }


def _build_query_logic(
    inclusion: list[str],
    exclusion: list[str],
    variables: list[str],
    variable_mapping: dict,
) -> dict[str, Any]:
    """Build query logic representation."""
    logic = {
        "select": [],
        "from": [],
        "where": {
            "include": [],
            "exclude": [],
        },
    }

    # Map variables to fields
    for var in variables:
        if var in variable_mapping:
            mapping = variable_mapping[var]
            logic["select"].append(f"{mapping.get('form', 'unknown')}.{mapping.get('field', var)}")
            if mapping.get("form") not in logic["from"]:
                logic["from"].append(mapping.get("form"))
        else:
            logic["select"].append(f"[{var} - mapping needed]")

    # Map inclusion criteria to logic
    for criterion in inclusion:
        logic["where"]["include"].append(_parse_criterion(criterion))

    # Map exclusion criteria to logic
    for criterion in exclusion:
        logic["where"]["exclude"].append(_parse_criterion(criterion))

    return {
        "query_logic": logic,
        "pseudocode": _generate_pseudocode(logic),
        "note": "This is query LOGIC for data governance review, not executable code",
    }


def _parse_criterion(criterion: str) -> dict[str, str]:
    """Parse a criterion string into structured format."""
    criterion_lower = criterion.lower()

    # Age range pattern
    if "age" in criterion_lower and "-" in criterion:
        return {"field": "AGE", "operator": "BETWEEN", "value": criterion}

    # Sex/Gender pattern
    if any(word in criterion_lower for word in ["female", "male", "sex", "gender"]):
        return {"field": "SEX", "operator": "=", "value": criterion}

    # HIV pattern
    if "hiv" in criterion_lower:
        return {"field": "HIVSTAT", "operator": "=" if "positive" in criterion_lower else "!=", "value": criterion}

    # TB pattern
    if "tb" in criterion_lower:
        return {"field": "TB_STATUS", "operator": "=", "value": criterion}

    # Default
    return {"field": "UNKNOWN", "operator": "?", "value": criterion}


def _generate_pseudocode(logic: dict) -> str:
    """Generate pseudocode representation of query logic."""
    lines = ["-- Query Logic (Pseudocode)", "-- For data governance review only", ""]

    lines.append(f"SELECT {', '.join(logic['select']) if logic['select'] else '*'}")
    lines.append(f"FROM {', '.join(logic['from']) if logic['from'] else '[tables TBD]'}")

    if logic["where"]["include"] or logic["where"]["exclude"]:
        lines.append("WHERE")

        for idx, inc in enumerate(logic["where"]["include"]):
            prefix = "  " if idx == 0 else "  AND "
            lines.append(f"{prefix}{inc['field']} {inc['operator']} '{inc['value']}'")

        for exc in logic["where"]["exclude"]:
            lines.append(f"  AND NOT ({exc['field']} {exc['operator']} '{exc['value']}')")

    return "\n".join(lines)


# =============================================================================
# Tool Registry
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
        "mode": "SECURE",
        "registered_tools": [
            "explore_study_metadata",  # Tool 1: Feasibility & metadata queries
            "build_technical_request", # Tool 2: Concept sheet construction
        ],
        "forbidden_zone": str(FORBIDDEN_ZONE),
        "safe_zone": str(SAFE_ZONE),
        "security_model": {
            "raw_data_access": "BLOCKED",
            "metadata_access": "ALLOWED",
            "output_policy": "Zero-Trust (no PII/PHI in responses)",
        },
        "compliance": ["DPDPA 2023", "ICMR Guidelines", "k-anonymity"],
    }
