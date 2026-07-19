"""Production encrypted storage envelope v1."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
from dataclasses import dataclass
from typing import NoReturn
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from document_intake.application.ports.storage import StorageKey
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.storage.errors import StorageError, StorageErrorCode

MAGIC = b"DIOSOBJ1"
FORMAT_VERSION = 1
ALGORITHM = "AES-256-GCM"
NONCE_LENGTH = 12
TAG_LENGTH = 16
MAX_HEADER_LENGTH = 4096
HEADER_LENGTH_SIZE = 4
_PREFIX_LENGTH = len(MAGIC) + HEADER_LENGTH_SIZE
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset(
    {
        "algorithm",
        "artifact_id",
        "artifact_kind",
        "format_version",
        "key_version",
        "nonce",
        "object_generation",
        "plaintext_length",
        "plaintext_sha256",
    }
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_header_bytes(header: dict[str, object]) -> bytes:
    return json.dumps(
        header,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _raise_format() -> NoReturn:
    raise StorageError(StorageErrorCode.ENVELOPE_FORMAT)


def _strict_int(value: object, *, positive: bool = False, exact: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _raise_format()
    assert isinstance(value, int)
    typed_value = value
    if exact is not None and typed_value != exact:
        _raise_format()
    if positive and typed_value <= 0:
        raise StorageError(StorageErrorCode.KEY_VERSION_INVALID)
    if typed_value < 0:
        _raise_format()
    return typed_value


@dataclass(frozen=True, slots=True)
class ParsedEnvelope:
    header: dict[str, object]
    ciphertext_and_tag: bytes

    @property
    def artifact_id(self) -> EntityId:
        return EntityId(UUID(str(self.header["artifact_id"])))

    def __repr__(self) -> str:
        return "ParsedEnvelope(<redacted>)"


def build_envelope(
    *,
    key: StorageKey,
    artifact_id: EntityId,
    artifact_kind: ArtifactKind,
    plaintext: bytes,
) -> bytes:
    if type(key) is not StorageKey:
        raise StorageError(StorageErrorCode.KEY_INVALID)
    if type(artifact_id) is not EntityId:
        _raise_format()
    if type(artifact_kind) is not ArtifactKind:
        _raise_format()
    if type(plaintext) is not bytes:
        _raise_format()

    nonce = os.urandom(NONCE_LENGTH)
    header: dict[str, object] = {
        "algorithm": ALGORITHM,
        "artifact_id": str(artifact_id),
        "artifact_kind": artifact_kind.value,
        "format_version": FORMAT_VERSION,
        "key_version": key.version,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "object_generation": 1,
        "plaintext_length": len(plaintext),
        "plaintext_sha256": sha256_hex(plaintext),
    }
    encoded_header = canonical_header_bytes(header)
    encoded_length = struct.pack(">I", len(encoded_header))
    aad = MAGIC + encoded_length + encoded_header
    ciphertext_and_tag: bytes = AESGCM(key.key_bytes).encrypt(nonce, plaintext, aad)
    return aad + ciphertext_and_tag


def parse_envelope(data: bytes) -> ParsedEnvelope:
    if type(data) is not bytes:
        _raise_format()
    if len(data) < _PREFIX_LENGTH + TAG_LENGTH:
        _raise_format()
    if data[: len(MAGIC)] != MAGIC:
        _raise_format()

    header_length = struct.unpack(">I", data[len(MAGIC) : _PREFIX_LENGTH])[0]
    if header_length == 0 or header_length > MAX_HEADER_LENGTH:
        _raise_format()
    header_end = _PREFIX_LENGTH + header_length
    if len(data) < header_end + TAG_LENGTH:
        _raise_format()

    encoded_header = data[_PREFIX_LENGTH:header_end]
    try:
        decoded_header = encoded_header.decode("utf-8")
        header = json.loads(decoded_header)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _raise_format()
    if not isinstance(header, dict):
        _raise_format()
    if set(header) != _FIELDS:
        _raise_format()
    typed_header = dict[str, object](header)
    if canonical_header_bytes(typed_header) != encoded_header:
        _raise_format()

    _validate_header(typed_header)
    ciphertext_and_tag = data[header_end:]
    plaintext_length = _strict_int(typed_header["plaintext_length"])
    if len(ciphertext_and_tag) != plaintext_length + TAG_LENGTH:
        _raise_format()
    return ParsedEnvelope(typed_header, ciphertext_and_tag)


def _validate_header(header: dict[str, object]) -> None:
    if header["algorithm"] != ALGORITHM:
        _raise_format()
    _strict_int(header["format_version"], exact=FORMAT_VERSION)
    _strict_int(header["object_generation"], exact=1)
    _strict_int(header["key_version"], positive=True)
    _strict_int(header["plaintext_length"])

    digest = header["plaintext_sha256"]
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        _raise_format()

    artifact_id_value = header["artifact_id"]
    if not isinstance(artifact_id_value, str):
        _raise_format()
    assert isinstance(artifact_id_value, str)
    try:
        parsed_uuid = UUID(artifact_id_value)
    except ValueError:
        _raise_format()
    if str(parsed_uuid) != artifact_id_value:
        _raise_format()

    artifact_kind_value = header["artifact_kind"]
    if not isinstance(artifact_kind_value, str):
        _raise_format()
    assert isinstance(artifact_kind_value, str)
    try:
        ArtifactKind(artifact_kind_value)
    except ValueError:
        _raise_format()

    encoded_nonce_value = header["nonce"]
    if not isinstance(encoded_nonce_value, str):
        _raise_format()
    assert isinstance(encoded_nonce_value, str)
    try:
        nonce = base64.b64decode(encoded_nonce_value, validate=True)
    except ValueError:
        _raise_format()
    if base64.b64encode(nonce).decode("ascii") != encoded_nonce_value:
        _raise_format()
    if len(nonce) != NONCE_LENGTH:
        _raise_format()


def decrypt_envelope(*, key: StorageKey, serialized: bytes) -> tuple[bytes, ParsedEnvelope]:
    if type(key) is not StorageKey:
        raise StorageError(StorageErrorCode.KEY_INVALID)
    parsed = parse_envelope(serialized)
    header = parsed.header
    if header["key_version"] != key.version:
        raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
    nonce = base64.b64decode(str(header["nonce"]), validate=True)
    header_length = struct.unpack(">I", serialized[len(MAGIC) : _PREFIX_LENGTH])[0]
    aad = serialized[: _PREFIX_LENGTH + header_length]
    try:
        plaintext = AESGCM(key.key_bytes).decrypt(nonce, parsed.ciphertext_and_tag, aad)
    except InvalidTag:
        raise StorageError(StorageErrorCode.AUTH_FAILED) from None
    if len(plaintext) != header["plaintext_length"]:
        raise StorageError(StorageErrorCode.EXPECTED_STATE_MISMATCH)
    if sha256_hex(plaintext) != header["plaintext_sha256"]:
        raise StorageError(StorageErrorCode.EXPECTED_STATE_MISMATCH)
    return plaintext, parsed
