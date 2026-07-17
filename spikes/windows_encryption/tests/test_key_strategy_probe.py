from __future__ import annotations

import os
from dataclasses import replace

import pytest

from spikes.windows_encryption.key_strategy_probe import (
    KeyPurpose,
    derive_kek,
    derive_purpose_key,
    generate_dek,
    unwrap_dek,
    wrap_dek,
)


def test_purpose_derivation_properties() -> None:
    pytest.importorskip("cryptography")
    root = os.urandom(32)
    salt = os.urandom(16)
    database = derive_purpose_key(root, salt, KeyPurpose.DATABASE)
    assert database == derive_purpose_key(root, salt, KeyPurpose.DATABASE)
    assert database != derive_purpose_key(root, salt, KeyPurpose.FILE)
    assert database != derive_purpose_key(root, os.urandom(16), KeyPurpose.DATABASE)
    assert database != root
    with pytest.raises(ValueError, match="ERR_INVALID_PURPOSE"):
        derive_purpose_key(root, salt, "artifact-0001")  # type: ignore[arg-type]


def test_wrapped_dek_binds_purpose_and_rejects_tamper() -> None:
    pytest.importorskip("cryptography")
    root = os.urandom(32)
    salt = os.urandom(16)
    db_dek = generate_dek()
    file_dek = generate_dek()
    assert db_dek != file_dek
    assert derive_kek(root, salt, KeyPurpose.DATABASE) != derive_kek(root, salt, KeyPurpose.FILE)
    wrapped = wrap_dek(root, salt, db_dek, KeyPurpose.DATABASE)
    assert unwrap_dek(root, salt, wrapped) == db_dek
    with pytest.raises(ValueError, match="ERR_DEK_UNWRAP_FAILED"):
        unwrap_dek(root, salt, replace(wrapped, purpose=KeyPurpose.FILE))
    with pytest.raises(ValueError, match="ERR_DEK_UNWRAP_FAILED"):
        unwrap_dek(os.urandom(32), salt, wrapped)
    tampered = replace(wrapped, wrapped=wrapped.wrapped[:-1] + bytes([wrapped.wrapped[-1] ^ 1]))
    with pytest.raises(ValueError, match="ERR_DEK_UNWRAP_FAILED"):
        unwrap_dek(root, salt, tampered)
