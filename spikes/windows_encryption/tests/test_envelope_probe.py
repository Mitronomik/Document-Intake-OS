from __future__ import annotations

import os
from dataclasses import replace

import pytest

from spikes.windows_encryption.envelope_probe import NonceRegistry, RollbackStatus, decrypt_envelope, encrypt_envelope, expected_state_for, verify_expected_state


def test_envelope_roundtrip_and_tamper() -> None:
    pytest.importorskip("cryptography")
    key = os.urandom(32)
    registry = NonceRegistry()
    env = encrypt_envelope(key, os.urandom(64), "artifact-0001", "application/octet-stream", 1, 1, registry)
    assert len(env.nonce) == 12
    assert decrypt_envelope(key, env, "artifact-0001", "application/octet-stream", 1)
    env2 = encrypt_envelope(key, os.urandom(64), "artifact-0001", "application/octet-stream", 2, 1, registry)
    assert env.nonce != env2.nonce
    with pytest.raises(ValueError, match="ERR_DUPLICATE_NONCE"):
        registry.remember(env.nonce)
    bad = replace(env, ciphertext=env.ciphertext[:-1] + bytes([env.ciphertext[-1] ^ 1]))
    with pytest.raises(ValueError, match="ERR_ENVELOPE_AUTH_FAILED"):
        decrypt_envelope(key, bad, "artifact-0001", "application/octet-stream", 1)
    with pytest.raises(ValueError, match="ERR_ENVELOPE_CONTEXT_MISMATCH"):
        decrypt_envelope(key, env, "artifact-0002", "application/octet-stream", 1)


def test_independent_rollback_anchor() -> None:
    pytest.importorskip("cryptography")
    key = os.urandom(32)
    old = encrypt_envelope(key, b"generation 1", "artifact-0001", "application/octet-stream", 1, 1)
    current = encrypt_envelope(key, b"generation 2", "artifact-0001", "application/octet-stream", 2, 1)
    record = expected_state_for(current)
    assert verify_expected_state(current, record) is RollbackStatus.PASS
    assert verify_expected_state(old, record) is RollbackStatus.FAIL
    copied = replace(current, metadata=replace(current.metadata, artifact_id="artifact-0002"))
    assert verify_expected_state(copied, record) is RollbackStatus.FAIL
