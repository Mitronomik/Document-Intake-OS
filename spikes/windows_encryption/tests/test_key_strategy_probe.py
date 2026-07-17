from __future__ import annotations

import os

import pytest

from spikes.windows_encryption.key_strategy_probe import derive_purpose_key, generate_dek, unwrap_dek, wrap_dek


def test_purpose_derivation_properties() -> None:
    root = os.urandom(32)
    salt = os.urandom(16)
    db1 = derive_purpose_key(root, salt, "database-key")
    assert db1 == derive_purpose_key(root, salt, "database-key")
    assert db1 != derive_purpose_key(root, salt, "file-key-encryption-key")
    assert db1 != derive_purpose_key(root, os.urandom(16), "database-key")
    assert db1 != root
    with pytest.raises(ValueError, match="ERR_INVALID_PURPOSE"):
        derive_purpose_key(root, salt, "artifact-0001")
    with pytest.raises(ValueError, match="ERR_WEAK_INPUT_KEY_MATERIAL"):
        derive_purpose_key(b"artifact-0001", salt, "database-key")


def test_wrapped_dek_roundtrip_when_cryptography_available() -> None:
    pytest.importorskip("cryptography")
    root = os.urandom(32)
    salt = os.urandom(16)
    dek = generate_dek()
    wrapped = wrap_dek(root, salt, dek, "database-key")
    assert unwrap_dek(root, salt, wrapped) == dek
    assert dek != root
    with pytest.raises(ValueError, match="ERR_DEK_UNWRAP_FAILED"):
        unwrap_dek(os.urandom(32), salt, wrapped)
