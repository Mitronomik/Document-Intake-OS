from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

VALID_PURPOSES = frozenset({"database-key", "file-key-encryption-key", "future-backup-key", "root-kek"})


@dataclass(frozen=True)
class WrappedDek:
    purpose: str
    wrapped: bytes


def derive_purpose_key(root_key: bytes, salt: bytes, purpose: str, length: int = 32) -> bytes:
    if purpose not in VALID_PURPOSES:
        raise ValueError("ERR_INVALID_PURPOSE")
    if len(root_key) < 32:
        raise ValueError("ERR_WEAK_INPUT_KEY_MATERIAL")
    prk = hmac.new(salt, root_key, hashlib.sha256).digest()
    info = b"pr-s001:" + purpose.encode("ascii")
    okm = b""
    prev = b""
    counter = 1
    while len(okm) < length:
        prev = hmac.new(prk, prev + info + bytes([counter]), hashlib.sha256).digest()
        okm += prev
        counter += 1
    return okm[:length]


def generate_dek() -> bytes:
    return os.urandom(32)


def wrap_dek(root_key: bytes, salt: bytes, dek: bytes, purpose: str) -> WrappedDek:
    try:
        from cryptography.hazmat.primitives.keywrap import aes_key_wrap_with_padding
    except ImportError as exc:  # pragma: no cover - dependency is Windows spike-only
        raise RuntimeError("ERR_CRYPTOGRAPHY_UNAVAILABLE") from exc
    kek = derive_purpose_key(root_key, salt, "root-kek")
    return WrappedDek(purpose=purpose, wrapped=aes_key_wrap_with_padding(kek, dek))


def unwrap_dek(root_key: bytes, salt: bytes, wrapped: WrappedDek) -> bytes:
    try:
        from cryptography.hazmat.primitives.keywrap import aes_key_unwrap_with_padding
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("ERR_CRYPTOGRAPHY_UNAVAILABLE") from exc
    kek = derive_purpose_key(root_key, salt, "root-kek")
    try:
        return aes_key_unwrap_with_padding(kek, wrapped.wrapped)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("ERR_DEK_UNWRAP_FAILED") from exc
