"""Tests for strict SQLCipher status normalization."""

from document_intake.persistence.database import _cipher_status_is_active


def test_cipher_status_accepts_canonical_active_values() -> None:
    for value in (1, "1", b"1"):
        assert _cipher_status_is_active(value)


def test_cipher_status_rejects_inactive_and_unknown_values() -> None:
    for value in (
        None,
        0,
        "0",
        b"0",
        True,
        False,
        "active",
        1.0,
        "",
        b"",
    ):
        assert not _cipher_status_is_active(value)
