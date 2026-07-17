from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

MAGIC = "SPIKE ENVELOPE VERSION 0"
FORMAT_VERSION = 0
ALGORITHM = "AES-256-GCM"
NONCE_LENGTH = 12
TAG_LENGTH = 16


class EnvelopeStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class EnvelopeMetadata:
    artifact_id: str
    artifact_kind: str
    plaintext_length: int
    object_generation: int
    key_version: int
    storage_format_version: int
    plaintext_sha256: str


@dataclass(frozen=True)
class Envelope:
    magic: str
    format_version: int
    algorithm: str
    key_version: int
    nonce: bytes
    metadata: EnvelopeMetadata
    ciphertext: bytes
    tag: bytes


@dataclass(frozen=True)
class ExpectedStateRecord:
    artifact_id: str
    expected_generation: int
    expected_plaintext_digest: str
    expected_ciphertext_digest: str
    key_version: int
    storage_format_version: int
    coordinated_rollback_detection: str = "NOT_CLAIMED"


class NonceRegistry:
    def __init__(self) -> None:
        self._seen: set[bytes] = set()

    def remember(self, nonce: bytes) -> None:
        if len(nonce) != NONCE_LENGTH:
            raise ValueError("ERR_INVALID_NONCE")
        if nonce in self._seen:
            raise ValueError("ERR_DUPLICATE_NONCE")
        self._seen.add(nonce)


def canonical_metadata(metadata: EnvelopeMetadata) -> bytes:
    payload = {
        "artifact_id": metadata.artifact_id,
        "artifact_kind": metadata.artifact_kind,
        "key_version": metadata.key_version,
        "object_generation": metadata.object_generation,
        "plaintext_length": metadata.plaintext_length,
        "plaintext_sha256": metadata.plaintext_sha256,
        "storage_format_version": metadata.storage_format_version,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _aad(envelope: Envelope) -> bytes:
    header = {
        "algorithm": envelope.algorithm,
        "format_version": envelope.format_version,
        "key_version": envelope.key_version,
        "magic": envelope.magic,
    }
    return (
        json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
        + canonical_metadata(envelope.metadata)
    )


def encrypt_envelope(
    key: bytes,
    plaintext: bytes,
    artifact_id: str,
    artifact_kind: str,
    generation: int,
    key_version: int,
    registry: NonceRegistry | None = None,
) -> Envelope:
    if len(key) != 32:
        raise ValueError("ERR_INVALID_KEY")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("ERR_CRYPTOGRAPHY_UNAVAILABLE") from exc
    nonce = os.urandom(NONCE_LENGTH)
    if registry is not None:
        registry.remember(nonce)
    metadata = EnvelopeMetadata(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        plaintext_length=len(plaintext),
        object_generation=generation,
        key_version=key_version,
        storage_format_version=FORMAT_VERSION,
        plaintext_sha256=hashlib.sha256(plaintext).hexdigest(),
    )
    shell = Envelope(MAGIC, FORMAT_VERSION, ALGORITHM, key_version, nonce, metadata, b"", b"")
    encrypted = AESGCM(key).encrypt(nonce, plaintext, _aad(shell))
    return replace(shell, ciphertext=encrypted[:-TAG_LENGTH], tag=encrypted[-TAG_LENGTH:])


def decrypt_envelope(
    key: bytes,
    envelope: Envelope,
    artifact_id: str,
    artifact_kind: str,
    key_version: int,
) -> bytes:
    if envelope.magic != MAGIC or envelope.format_version != FORMAT_VERSION:
        raise ValueError("ERR_ENVELOPE_FORMAT")
    if envelope.algorithm != ALGORITHM or len(envelope.nonce) != NONCE_LENGTH:
        raise ValueError("ERR_ENVELOPE_FORMAT")
    if (
        envelope.metadata.artifact_id != artifact_id
        or envelope.metadata.artifact_kind != artifact_kind
        or envelope.key_version != key_version
        or envelope.metadata.key_version != key_version
    ):
        raise ValueError("ERR_ENVELOPE_CONTEXT_MISMATCH")
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("ERR_CRYPTOGRAPHY_UNAVAILABLE") from exc
    try:
        plaintext = AESGCM(key).decrypt(
            envelope.nonce,
            envelope.ciphertext + envelope.tag,
            _aad(envelope),
        )
    except InvalidTag as exc:
        raise ValueError("ERR_ENVELOPE_AUTH_FAILED") from exc
    if len(plaintext) != envelope.metadata.plaintext_length:
        raise ValueError("ERR_ENVELOPE_LENGTH_MISMATCH")
    if hashlib.sha256(plaintext).hexdigest() != envelope.metadata.plaintext_sha256:
        raise ValueError("ERR_ENVELOPE_DIGEST_MISMATCH")
    return plaintext


def envelope_to_bytes(envelope: Envelope) -> bytes:
    payload: dict[str, Any] = {
        "algorithm": envelope.algorithm,
        "ciphertext": base64.b64encode(envelope.ciphertext).decode("ascii"),
        "format_version": envelope.format_version,
        "key_version": envelope.key_version,
        "magic": envelope.magic,
        "metadata": json.loads(canonical_metadata(envelope.metadata).decode("utf-8")),
        "nonce": base64.b64encode(envelope.nonce).decode("ascii"),
        "tag": base64.b64encode(envelope.tag).decode("ascii"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def ciphertext_digest(envelope: Envelope) -> str:
    return hashlib.sha256(envelope_to_bytes(envelope)).hexdigest()


def expected_state_for(envelope: Envelope) -> ExpectedStateRecord:
    return ExpectedStateRecord(
        artifact_id=envelope.metadata.artifact_id,
        expected_generation=envelope.metadata.object_generation,
        expected_plaintext_digest=envelope.metadata.plaintext_sha256,
        expected_ciphertext_digest=ciphertext_digest(envelope),
        key_version=envelope.key_version,
        storage_format_version=envelope.metadata.storage_format_version,
    )


def verify_expected_state(envelope: Envelope, record: ExpectedStateRecord) -> EnvelopeStatus:
    if (
        envelope.metadata.artifact_id == record.artifact_id
        and envelope.metadata.object_generation == record.expected_generation
        and envelope.metadata.plaintext_sha256 == record.expected_plaintext_digest
        and ciphertext_digest(envelope) == record.expected_ciphertext_digest
        and envelope.key_version == record.key_version
        and envelope.metadata.storage_format_version == record.storage_format_version
    ):
        return EnvelopeStatus.PASS
    return EnvelopeStatus.FAIL


def no_plaintext_temp_file(temp_dir: Path, plaintext: bytes) -> bool:
    return all(plaintext not in path.read_bytes() for path in temp_dir.rglob("*") if path.is_file())
