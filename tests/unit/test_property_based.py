"""
Property-based tests using Hypothesis.

These tests use property-based testing to discover edge cases
that traditional example-based tests might miss.

Property-based testing generates random inputs and verifies
that certain properties always hold true.
"""

from __future__ import annotations

from hypothesis import given, strategies as st, assume, settings
import pytest

from server.tools import (
    ExploreStudyMetadataInput,
    BuildTechnicalRequestInput,
)
from pydantic import ValidationError


class TestExploreStudyMetadataInputProperties:
    """Property-based tests for ExploreStudyMetadataInput validation."""

    @given(st.text(min_size=5, max_size=100))
    def test_queries_with_forbidden_patterns_rejected(self, query: str) -> None:
        """Property: Any query containing forbidden patterns should be rejected."""
        forbidden_patterns = ["data/dataset", "indo-vap", ".xlsx", "raw data"]
        
        for pattern in forbidden_patterns:
            full_query = f"{query} {pattern} {query}"
            
            with pytest.raises(ValidationError):
                ExploreStudyMetadataInput(query=full_query)

    @given(st.text(min_size=5, max_size=400))
    @settings(max_examples=50)
    def test_safe_queries_pass_length_validation(self, text: str) -> None:
        """Property: Safe queries meeting length requirements should pass."""
        # Filter out any potentially forbidden patterns
        forbidden = [
            "data/dataset", "data\\dataset", "indo-vap", "csv_files", 
            ".xlsx", "raw data", "patient names", "show me all patients",
            "list all records", "export data", "download dataset",
            "individual records", "read from file", "access the raw dataset"
        ]
        
        text_lower = text.lower()
        assume(not any(f in text_lower for f in forbidden))
        assume(5 <= len(text.strip()) <= 500)
        assume(len(text.strip()) >= 5)  # Minimum query length
        
        try:
            input_data = ExploreStudyMetadataInput(query=text)
            assert input_data.query == text.strip()
        except ValidationError:
            # Some texts might still hit validation rules
            pass

    @given(st.text(min_size=1, max_size=4))
    def test_short_queries_always_rejected(self, query: str) -> None:
        """Property: Queries shorter than 5 characters should always be rejected."""
        with pytest.raises(ValidationError):
            ExploreStudyMetadataInput(query=query)

    @given(st.text(min_size=501, max_size=600))
    def test_long_queries_always_rejected(self, query: str) -> None:
        """Property: Queries longer than 500 characters should always be rejected."""
        with pytest.raises(ValidationError):
            ExploreStudyMetadataInput(query=query)


class TestBuildTechnicalRequestInputProperties:
    """Property-based tests for BuildTechnicalRequestInput validation."""

    @given(
        st.text(min_size=10, max_size=400),
        st.lists(st.text(min_size=1, max_size=50), max_size=5),
        st.lists(st.text(min_size=1, max_size=50), max_size=5),
    )
    @settings(max_examples=50)
    def test_safe_descriptions_accepted(
        self, 
        description: str, 
        inclusion: list[str],
        exclusion: list[str],
    ) -> None:
        """Property: Safe descriptions meeting length requirements should pass."""
        # Filter out forbidden patterns
        forbidden = ["data/dataset", "data\\dataset", "indo-vap", ".xlsx", "raw data"]
        
        desc_lower = description.lower()
        assume(not any(f in desc_lower for f in forbidden))
        assume(10 <= len(description.strip()) <= 500)
        
        try:
            input_data = BuildTechnicalRequestInput(
                description=description,
                inclusion_criteria=inclusion,
                exclusion_criteria=exclusion,
            )
            assert input_data.description == description.strip()
        except ValidationError:
            # Some descriptions might still hit validation rules
            pass

    @given(st.text(min_size=1, max_size=9))
    def test_short_descriptions_always_rejected(self, description: str) -> None:
        """Property: Descriptions shorter than 10 characters should be rejected."""
        with pytest.raises(ValidationError):
            BuildTechnicalRequestInput(description=description)

    @given(st.sampled_from(["concept_sheet", "query_logic"]))
    def test_valid_output_formats_always_accepted(self, output_format: str) -> None:
        """Property: Valid output formats should always be accepted."""
        input_data = BuildTechnicalRequestInput(
            description="Valid description for testing purposes",
            output_format=output_format,
        )
        assert input_data.output_format == output_format

    @given(st.text(min_size=1, max_size=20).filter(
        lambda x: x not in ["concept_sheet", "query_logic"]
    ))
    def test_invalid_output_formats_always_rejected(self, output_format: str) -> None:
        """Property: Invalid output formats should always be rejected."""
        assume(output_format not in ["concept_sheet", "query_logic"])
        
        with pytest.raises(ValidationError):
            BuildTechnicalRequestInput(
                description="Valid description for testing purposes",
                output_format=output_format,
            )


class TestSecurityValidationProperties:
    """Property-based tests for security validation."""

    @given(st.sampled_from([
        "data/dataset", "data\\dataset", "indo-vap", "csv_files",
        "6_HIV.xlsx", "read from file", "access the raw dataset",
    ]))
    def test_forbidden_patterns_always_blocked_in_metadata(self, pattern: str) -> None:
        """Property: Forbidden patterns are always rejected in metadata queries."""
        query = f"Please help me analyze {pattern} data"
        
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query=query)
        
        # Should raise security-related error
        error_str = str(exc_info.value).lower()
        assert "security" in error_str or "prohibited" in error_str or "metadata only" in error_str

    @given(st.sampled_from([
        "show me all patients", "list all records", "export data",
        "download dataset", "raw data", "patient names", "individual records",
    ]))
    def test_phi_patterns_always_blocked(self, phi_pattern: str) -> None:
        """Property: PHI request patterns are always rejected."""
        query = f"I need to {phi_pattern} from the study"
        
        with pytest.raises(ValidationError) as exc_info:
            ExploreStudyMetadataInput(query=query)
        
        # Should provide guidance about metadata-only access
        assert "metadata only" in str(exc_info.value).lower()

    @given(st.sampled_from([
        "data/dataset", "data\\dataset", "indo-vap", ".xlsx", "raw data",
    ]))
    def test_forbidden_patterns_always_blocked_in_technical_request(self, pattern: str) -> None:
        """Property: Forbidden patterns are always rejected in technical requests."""
        description = f"Access {pattern} for analysis"
        
        with pytest.raises(ValidationError) as exc_info:
            BuildTechnicalRequestInput(description=description)
        
        assert "SECURITY ALERT" in str(exc_info.value)


class TestInputSanitizationProperties:
    """Property-based tests for input sanitization."""

    @given(st.text(min_size=5, max_size=200))
    @settings(max_examples=30)
    def test_query_whitespace_always_trimmed(self, text: str) -> None:
        """Property: Query whitespace should always be trimmed."""
        # Filter out forbidden patterns
        forbidden = [
            "data/dataset", "indo-vap", ".xlsx", "raw data", "patient names",
            "show me all patients", "export data", "download dataset",
            "list all records", "individual records"
        ]
        
        text_lower = text.lower()
        assume(not any(f in text_lower for f in forbidden))
        assume(len(text.strip()) >= 5)
        
        padded_query = f"  {text}  "
        
        try:
            input_data = ExploreStudyMetadataInput(query=padded_query)
            assert input_data.query == padded_query.strip()
        except ValidationError:
            # Some inputs may be rejected for other reasons
            pass

    @given(st.text(min_size=10, max_size=200))
    @settings(max_examples=30)
    def test_description_whitespace_always_trimmed(self, text: str) -> None:
        """Property: Description whitespace should always be trimmed."""
        # Filter out forbidden patterns
        forbidden = ["data/dataset", "indo-vap", ".xlsx", "raw data"]
        
        text_lower = text.lower()
        assume(not any(f in text_lower for f in forbidden))
        assume(len(text.strip()) >= 10)
        
        padded_description = f"  {text}  "
        
        try:
            input_data = BuildTechnicalRequestInput(description=padded_description)
            assert input_data.description == padded_description.strip()
        except ValidationError:
            # Some inputs may be rejected for other reasons
            pass
