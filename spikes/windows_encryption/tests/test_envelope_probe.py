from __future__ import annotations

import os
from dataclasses import replace

import pytest

from spikes.windows_encryption.envelope_probe import (
    EnvelopeStatus,
    NonceRegistry,
    decrypt_envelope,
    encrypt_envelope,
    envelope_to_bytes,
    expected_state_for,
    no_plaintext_temp_file,
    verify_expected_state,
)


def _env() -> tuple[bytes, bytes, object]:
    key = os.urandom(32)
    plaintext = os.urandom(64)
    envelope = encrypt_envelope(key, plaintext, "artifact-0001", "application-octet-stream", 1, 1)
    return key, plaintext, envelope


def test_byte_identical_roundtrip_and_nonce_registry(tmp_path) -> None:
    pytest.importorskip("cryptography")
    key, plaintext, envelope = _env()
    assert (
        decrypt_envelope(key, envelope, "artifact-0001", "application-octet-stream", 1) == plaintext
    )
    assert envelope_to_bytes(envelope) == envelope_to_bytes(envelope)
    assert len(envelope.nonce) == 12
    registry = NonceRegistry()
    registry.remember(envelope.nonce)
    with pytest.raises(ValueError, match="ERR_DUPLICATE_NONCE"):
        registry.remember(envelope.nonce)
    other = encrypt_envelope(key, plaintext, "artifact-0001", "application-octet-stream", 2, 1)
    assert other.nonce != envelope.nonce
    assert no_plaintext_temp_file(tmp_path, plaintext)


def test_tamper_matrix_returns_stable_errors() -> None:
    pytest.importorskip("cryptography")
    key, plaintext, envelope = _env()
    cases = [
        replace(
            envelope, ciphertext=envelope.ciphertext[:-1] + bytes([envelope.ciphertext[-1] ^ 1])
        ),
        replace(envelope, tag=envelope.tag[:-1] + bytes([envelope.tag[-1] ^ 1])),
        replace(envelope, ciphertext=envelope.ciphertext[:-3]),
        replace(envelope, metadata=replace(envelope.metadata, object_generation=2)),
        replace(envelope, metadata=replace(envelope.metadata, plaintext_length=len(plaintext) + 1)),
        replace(envelope, metadata=replace(envelope.metadata, plaintext_sha256="0" * 64)),
    ]
    for case in cases:
        with pytest.raises(
            ValueError, match=r"ERR_ENVELOPE_AUTH_FAILED|ERR_ENVELOPE_LENGTH_MISMATCH"
        ):
            decrypt_envelope(key, case, "artifact-0001", "application-octet-stream", 1)
    with pytest.raises(ValueError, match="ERR_ENVELOPE_CONTEXT_MISMATCH"):
        decrypt_envelope(key, envelope, "artifact-0002", "application-octet-stream", 1)
    with pytest.raises(ValueError, match="ERR_ENVELOPE_CONTEXT_MISMATCH"):
        decrypt_envelope(key, envelope, "artifact-0001", "other-kind", 1)
    with pytest.raises(ValueError, match="ERR_ENVELOPE_CONTEXT_MISMATCH"):
        decrypt_envelope(key, envelope, "artifact-0001", "application-octet-stream", 2)
    with pytest.raises(ValueError, match="ERR_ENVELOPE_AUTH_FAILED"):
        decrypt_envelope(os.urandom(32), envelope, "artifact-0001", "application-octet-stream", 1)


def test_independent_rollback_anchor_matrix() -> None:
    pytest.importorskip("cryptography")
    key = os.urandom(32)
    old = encrypt_envelope(key, b"generation 1", "artifact-0001", "application-octet-stream", 1, 1)
    current = encrypt_envelope(
        key, b"generation 2", "artifact-0001", "application-octet-stream", 2, 1
    )
    record = expected_state_for(current)
    assert verify_expected_state(current, record) is EnvelopeStatus.PASS
    assert verify_expected_state(old, record) is EnvelopeStatus.FAIL
    assert (
        verify_expected_state(
            replace(current, metadata=replace(current.metadata, object_generation=1)), record
        )
        is EnvelopeStatus.FAIL
    )
    assert (
        verify_expected_state(
            replace(
                current,
                metadata=replace(current.metadata, plaintext_sha256=old.metadata.plaintext_sha256),
            ),
            record,
        )
        is EnvelopeStatus.FAIL
    )
    assert verify_expected_state(replace(current, key_version=0), record) is EnvelopeStatus.FAIL
    assert (
        verify_expected_state(replace(current, ciphertext=old.ciphertext), record)
        is EnvelopeStatus.FAIL
    )
    assert (
        verify_expected_state(
            replace(current, metadata=replace(current.metadata, artifact_id="artifact-0002")),
            record,
        )
        is EnvelopeStatus.FAIL
    )
    assert expected_state_for(old).coordinated_rollback_detection == "NOT_CLAIMED"
