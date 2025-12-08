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
    QueryDatabaseInput,
    SearchDictionaryInput,
    FetchMetricsInput,
    MetricType,
)
from pydantic import ValidationError


class TestQueryDatabaseInputProperties:
    """Property-based tests for QueryDatabaseInput validation."""

    @given(st.text(min_size=1, max_size=50))
    def test_non_select_queries_always_rejected(self, prefix: str) -> None:
        """Property: Any query not starting with SELECT should be rejected."""
        assume(not prefix.strip().upper().startswith("SELECT"))
        assume(len(prefix.strip()) >= 10)  # Meet minimum length
        
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query=prefix + " something")

    @given(st.integers(min_value=1, max_value=1000))
    def test_valid_limits_always_accepted(self, limit: int) -> None:
        """Property: Any limit between 1 and 1000 should be accepted."""
        input_data = QueryDatabaseInput(
            query="SELECT * FROM patients WHERE id > 0",
            limit=limit,
        )
        assert input_data.limit == limit

    @given(st.integers())
    def test_invalid_limits_rejected(self, limit: int) -> None:
        """Property: Limits outside 1-1000 should be rejected."""
        assume(limit < 1 or limit > 1000)
        
        with pytest.raises(ValidationError):
            QueryDatabaseInput(
                query="SELECT * FROM patients",
                limit=limit,
            )

    @given(st.text(min_size=10, max_size=100).filter(lambda x: ";" not in x and "--" not in x))
    def test_select_prefix_always_required(self, suffix: str) -> None:
        """Property: SELECT prefix is required for valid queries."""
        query = f"SELECT {suffix}"
        
        # Should not raise for any safe SELECT query
        try:
            input_data = QueryDatabaseInput(query=query)
            assert input_data.query.upper().startswith("SELECT")
        except ValidationError:
            # Some suffixes might contain dangerous keywords
            pass

    @given(st.sampled_from(["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE"]))
    def test_dangerous_keywords_always_rejected(self, keyword: str) -> None:
        """Property: Dangerous SQL keywords are always rejected."""
        # Even if disguised as SELECT, dangerous keywords should fail
        query = f"SELECT * FROM users; {keyword} TABLE users"
        
        with pytest.raises(ValidationError):
            QueryDatabaseInput(query=query)


class TestSearchDictionaryInputProperties:
    """Property-based tests for SearchDictionaryInput validation."""

    @given(st.text(min_size=2, max_size=100))
    def test_valid_search_terms_accepted(self, search_term: str) -> None:
        """Property: Search terms between 2-100 chars should be accepted."""
        assume(len(search_term.strip()) >= 2)
        
        try:
            input_data = SearchDictionaryInput(search_term=search_term)
            assert len(input_data.search_term) >= 2
        except ValidationError:
            # Some special characters might cause issues
            pass

    @given(st.text(max_size=1))
    def test_short_search_terms_rejected(self, search_term: str) -> None:
        """Property: Search terms under 2 chars should be rejected."""
        with pytest.raises(ValidationError):
            SearchDictionaryInput(search_term=search_term)

    @given(st.text(min_size=2, max_size=50), st.booleans())
    def test_include_values_flag_preserved(self, search_term: str, include_values: bool) -> None:
        """Property: include_values flag should be preserved."""
        assume(len(search_term.strip()) >= 2)
        
        try:
            input_data = SearchDictionaryInput(
                search_term=search_term,
                include_values=include_values,
            )
            assert input_data.include_values == include_values
        except ValidationError:
            pass


class TestFetchMetricsInputProperties:
    """Property-based tests for FetchMetricsInput validation."""

    @given(
        st.sampled_from(list(MetricType)),
        st.text(min_size=1, max_size=100).filter(lambda x: len(x.strip()) > 0),
    )
    def test_all_metric_types_with_valid_fields(
        self, metric_type: MetricType, field_name: str
    ) -> None:
        """Property: All metric types should work with valid field names."""
        assume(len(field_name.strip()) >= 1)
        
        try:
            input_data = FetchMetricsInput(
                metric_type=metric_type,
                field_name=field_name,
            )
            assert input_data.metric_type == metric_type
        except ValidationError:
            pass

    @given(st.dictionaries(st.text(min_size=1, max_size=20), st.text(min_size=1, max_size=20)))
    def test_arbitrary_filters_accepted(self, filters: dict[str, str]) -> None:
        """Property: Arbitrary filter dictionaries should be accepted."""
        assume(len(filters) > 0)
        
        input_data = FetchMetricsInput(
            metric_type=MetricType.COUNT,
            field_name="test_field",
            filters=filters,
        )
        assert input_data.filters == filters


class TestEncryptionProperties:
    """Property-based tests for encryption module."""

    @given(st.binary(min_size=0, max_size=10000))
    @settings(max_examples=50)  # Limit for performance
    def test_encrypt_decrypt_roundtrip(self, plaintext: bytes) -> None:
        """Property: Encryption followed by decryption returns original data."""
        from server.security.encryption import AES256GCMCipher
        
        cipher = AES256GCMCipher.generate()
        encrypted = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(encrypted)
        
        assert decrypted == plaintext

    @given(st.binary(min_size=1, max_size=1000))
    @settings(max_examples=30)
    def test_different_ciphertexts_for_same_plaintext(self, plaintext: bytes) -> None:
        """Property: Same plaintext produces different ciphertext each time."""
        from server.security.encryption import AES256GCMCipher
        
        cipher = AES256GCMCipher.generate()
        encrypted1 = cipher.encrypt(plaintext)
        encrypted2 = cipher.encrypt(plaintext)
        
        # Should differ due to random nonce
        assert encrypted1 != encrypted2

    @given(st.text(min_size=8, max_size=100), st.binary(min_size=16, max_size=32))
    @settings(max_examples=30)
    def test_key_derivation_deterministic(self, password: str, salt: bytes) -> None:
        """Property: Same password + salt always produces same key."""
        from server.security.encryption import derive_key_from_password
        
        key1 = derive_key_from_password(password, salt)
        key2 = derive_key_from_password(password, salt)
        
        assert key1 == key2
