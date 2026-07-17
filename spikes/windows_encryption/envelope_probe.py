from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import Enum

MAGIC = b"SPIKE-ENVELOPE-V0\0"
ALGORITHM = "AES-256-GCM"
STORAGE_FORMAT_VERSION = 0


class RollbackStatus(str, Enum):
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
    metadata: EnvelopeMetadata
    nonce: bytes
    ciphertext: bytes


@dataclass(frozen=True)
class ExpectedStateRecord:
    artifact_id: str
    expected_generation: int
    expected_plaintext_digest: str
    expected_ciphertext_digest: str
    key_version: int
    storage_format_version: int


class NonceRegistry:
    def __init__(self) -> None:
        self._seen: set[bytes] = set()

    def remember(self, nonce: bytes) -> None:
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
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def encrypt_envelope(key: bytes, plaintext: bytes, artifact_id: str, artifact_kind: str, generation: int, key_version: int, registry: NonceRegistry | None = None) -> Envelope:
    if len(key) != 32:
        raise ValueError("ERR_INVALID_KEY")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("ERR_CRYPTOGRAPHY_UNAVAILABLE") from exc
    metadata = EnvelopeMetadata(artifact_id, artifact_kind, len(plaintext), generation, key_version, STORAGE_FORMAT_VERSION, hashlib.sha256(plaintext).hexdigest())
    nonce = os.urandom(12)
    if registry is not None:
        registry.remember(nonce)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, MAGIC + canonical_metadata(metadata))
    return Envelope(metadata, nonce, ciphertext)


def decrypt_envelope(key: bytes, envelope: Envelope, artifact_id: str, artifact_kind: str, key_version: int) -> bytes:
    if envelope.metadata.artifact_id != artifact_id or envelope.metadata.artifact_kind != artifact_kind or envelope.metadata.key_version != key_version:
        raise ValueError("ERR_ENVELOPE_CONTEXT_MISMATCH")
    if len(envelope.nonce) != 12:
        raise ValueError("ERR_INVALID_NONCE")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        plaintext = AESGCM(key).decrypt(envelope.nonce, envelope.ciphertext, MAGIC + canonical_metadata(envelope.metadata))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("ERR_ENVELOPE_AUTH_FAILED") from exc
    if len(plaintext) != envelope.metadata.plaintext_length or hashlib.sha256(plaintext).hexdigest() != envelope.metadata.plaintext_sha256:
        raise ValueError("ERR_ENVELOPE_METADATA_MISMATCH")
    return plaintext


def ciphertext_digest(envelope: Envelope) -> str:
    return hashlib.sha256(envelope.nonce + envelope.ciphertext).hexdigest()


def expected_state_for(envelope: Envelope) -> ExpectedStateRecord:
    return ExpectedStateRecord(envelope.metadata.artifact_id, envelope.metadata.object_generation, envelope.metadata.plaintext_sha256, ciphertext_digest(envelope), envelope.metadata.key_version, envelope.metadata.storage_format_version)


def verify_expected_state(envelope: Envelope, record: ExpectedStateRecord) -> RollbackStatus:
    if (envelope.metadata.artifact_id == record.artifact_id and envelope.metadata.object_generation == record.expected_generation and envelope.metadata.plaintext_sha256 == record.expected_plaintext_digest and ciphertext_digest(envelope) == record.expected_ciphertext_digest and envelope.metadata.key_version == record.key_version and envelope.metadata.storage_format_version == record.storage_format_version):
        return RollbackStatus.PASS
    return RollbackStatus.FAIL
