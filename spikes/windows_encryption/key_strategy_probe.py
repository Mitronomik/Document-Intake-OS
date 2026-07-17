from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast


class KeyPurpose(StrEnum):
    DATABASE = "database-key"
    FILE = "file-key-encryption-key"
    BACKUP = "future-backup-key"


@dataclass(frozen=True)
class WrappedDek:
    purpose: KeyPurpose
    wrapped: bytes


def _hkdf(root_key: bytes, salt: bytes, label: str) -> bytes:
    if len(root_key) != 32:
        raise ValueError("ERR_INVALID_ROOT_KEY")
    try:
        hashes_mod = cast(Any, importlib.import_module("cryptography.hazmat.primitives.hashes"))
        hkdf_mod = cast(Any, importlib.import_module("cryptography.hazmat.primitives.kdf.hkdf"))
        hashes = hashes_mod
        HKDF = hkdf_mod.HKDF
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("ERR_CRYPTOGRAPHY_UNAVAILABLE") from exc
    return bytes(
        HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=("pr-s001:" + label).encode("ascii"),
        ).derive(root_key)
    )


def derive_purpose_key(root_key: bytes, salt: bytes, purpose: KeyPurpose) -> bytes:
    if not isinstance(purpose, KeyPurpose):
        raise ValueError("ERR_INVALID_PURPOSE")
    return _hkdf(root_key, salt, purpose.value)


def generate_dek() -> bytes:
    return os.urandom(32)


def derive_kek(root_key: bytes, salt: bytes, purpose: KeyPurpose) -> bytes:
    if not isinstance(purpose, KeyPurpose):
        raise ValueError("ERR_INVALID_PURPOSE")
    return _hkdf(root_key, salt, "wrapped-dek:" + purpose.value)


def wrap_dek(root_key: bytes, salt: bytes, dek: bytes, purpose: KeyPurpose) -> WrappedDek:
    try:
        keywrap_mod = cast(
            Any,
            importlib.import_module("cryptography.hazmat.primitives.keywrap"),
        )
        aes_key_wrap_with_padding = keywrap_mod.aes_key_wrap_with_padding
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("ERR_CRYPTOGRAPHY_UNAVAILABLE") from exc
    return WrappedDek(
        purpose=purpose, wrapped=aes_key_wrap_with_padding(derive_kek(root_key, salt, purpose), dek)
    )


def unwrap_dek(root_key: bytes, salt: bytes, wrapped: WrappedDek) -> bytes:
    try:
        keywrap_mod = cast(
            Any,
            importlib.import_module("cryptography.hazmat.primitives.keywrap"),
        )
        aes_key_unwrap_with_padding = keywrap_mod.aes_key_unwrap_with_padding
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("ERR_CRYPTOGRAPHY_UNAVAILABLE") from exc
    try:
        return bytes(
            aes_key_unwrap_with_padding(
                derive_kek(root_key, salt, wrapped.purpose), wrapped.wrapped
            )
        )
    except ValueError as exc:
        raise ValueError("ERR_DEK_UNWRAP_FAILED") from exc
