"""
Unit tests for encryption module.

Tests cover:
- AES-256-GCM encryption/decryption
- Key generation and derivation
- Error handling
- Payload structure
"""

from __future__ import annotations

import base64

import pytest

from server.security.encryption import (
    AES_256_KEY_SIZE,
    AES256GCMCipher,
    DecryptionError,
    derive_key_from_password,
)


class TestAES256GCMCipher:
    """Tests for AES-256-GCM cipher operations."""

    def test_generate_creates_valid_cipher(self) -> None:
        """Test that generate() creates a cipher with valid key."""
        cipher = AES256GCMCipher.generate()

        assert cipher is not None
        assert len(cipher._key) == AES_256_KEY_SIZE

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test that encryption followed by decryption returns original data."""
        cipher = AES256GCMCipher.generate()
        plaintext = b"This is sensitive PHI data"

        encrypted = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_produces_different_output(self) -> None:
        """Test that encrypting same data twice produces different ciphertext."""
        cipher = AES256GCMCipher.generate()
        plaintext = b"Same data"

        encrypted1 = cipher.encrypt(plaintext)
        encrypted2 = cipher.encrypt(plaintext)

        # Should differ due to random nonce
        assert encrypted1 != encrypted2

    def test_decrypt_with_wrong_key_fails(self) -> None:
        """Test that decryption with wrong key raises error."""
        cipher1 = AES256GCMCipher.generate()
        cipher2 = AES256GCMCipher.generate()
        plaintext = b"Secret data"

        encrypted = cipher1.encrypt(plaintext)

        with pytest.raises(DecryptionError):
            cipher2.decrypt(encrypted)

    def test_decrypt_tampered_data_fails(self) -> None:
        """Test that decryption of tampered data raises error."""
        cipher = AES256GCMCipher.generate()
        plaintext = b"Original data"

        encrypted = cipher.encrypt(plaintext)
        # Tamper with the ciphertext
        tampered = encrypted[:-1] + bytes([encrypted[-1] ^ 0xFF])

        with pytest.raises(DecryptionError):
            cipher.decrypt(tampered)

    def test_export_import_key_roundtrip(self) -> None:
        """Test that exported key can be imported and used."""
        cipher1 = AES256GCMCipher.generate()
        plaintext = b"Test data for key export"

        encrypted = cipher1.encrypt(plaintext)
        key_b64 = cipher1.export_key()

        cipher2 = AES256GCMCipher.from_key(key_b64)
        decrypted = cipher2.decrypt(encrypted)

        assert decrypted == plaintext

    def test_export_key_is_base64(self) -> None:
        """Test that exported key is valid base64."""
        cipher = AES256GCMCipher.generate()
        key_b64 = cipher.export_key()

        # Should not raise
        decoded = base64.b64decode(key_b64)
        assert len(decoded) == AES_256_KEY_SIZE

    def test_from_key_invalid_length_fails(self) -> None:
        """Test that importing key with wrong length raises error."""
        invalid_key = base64.b64encode(b"short").decode()

        with pytest.raises(ValueError):
            AES256GCMCipher.from_key(invalid_key)

    def test_encrypt_empty_data(self) -> None:
        """Test encrypting empty data."""
        cipher = AES256GCMCipher.generate()

        encrypted = cipher.encrypt(b"")
        decrypted = cipher.decrypt(encrypted)

        assert decrypted == b""

    def test_encrypt_large_data(self) -> None:
        """Test encrypting large data."""
        cipher = AES256GCMCipher.generate()
        plaintext = b"x" * (1024 * 1024)  # 1MB

        encrypted = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(encrypted)

        assert decrypted == plaintext


class TestKeyDerivation:
    """Tests for password-based key derivation."""

    def test_derive_key_from_password(self) -> None:
        """Test deriving key from password."""
        password = "secure-password-123"
        salt = b"random-salt-value-"

        key = derive_key_from_password(password, salt)

        assert len(key) == AES_256_KEY_SIZE

    def test_same_password_salt_produces_same_key(self) -> None:
        """Test that same password and salt produce same key."""
        password = "test-password"
        salt = b"fixed-salt-12345"

        key1 = derive_key_from_password(password, salt)
        key2 = derive_key_from_password(password, salt)

        assert key1 == key2

    def test_different_salt_produces_different_key(self) -> None:
        """Test that different salt produces different key."""
        password = "test-password"

        key1 = derive_key_from_password(password, b"salt1-value")
        key2 = derive_key_from_password(password, b"salt2-value")

        assert key1 != key2

    def test_different_password_produces_different_key(self) -> None:
        """Test that different password produces different key."""
        salt = b"same-salt-value"

        key1 = derive_key_from_password("password1", salt)
        key2 = derive_key_from_password("password2", salt)

        assert key1 != key2
