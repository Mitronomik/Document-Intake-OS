from __future__ import annotations

import base64
import json
import struct
from uuid import uuid4

import pytest

from document_intake.application.ports.storage import StorageKey
from document_intake.domain.enums import ArtifactKind
from document_intake.storage.envelope import (
    MAGIC,
    NONCE_LENGTH,
    TAG_LENGTH,
    build_envelope,
    canonical_header_bytes,
    decrypt_envelope,
    parse_envelope,
)
from document_intake.storage.errors import StorageError, StorageErrorCode

from .conftest import KEY_BYTES, OTHER_KEY_BYTES, entity_id


def _header(envelope: bytes) -> tuple[dict[str, object], bytes]:
    length = struct.unpack(">I", envelope[8:12])[0]
    return json.loads(envelope[12 : 12 + length]), envelope[12 + length :]


def _replace_header(envelope: bytes, header: dict[str, object]) -> bytes:
    encoded = canonical_header_bytes(header)
    return MAGIC + struct.pack(">I", len(encoded)) + encoded + _header(envelope)[1]


def _noncanonical_header(envelope: bytes, header: dict[str, object]) -> bytes:
    encoded = json.dumps(header, sort_keys=False).encode("utf-8")
    return MAGIC + struct.pack(">I", len(encoded)) + encoded + _header(envelope)[1]


def assert_storage_error(
    data: bytes, code: StorageErrorCode = StorageErrorCode.ENVELOPE_FORMAT
) -> None:
    with pytest.raises(StorageError) as error:
        parse_envelope(data)
    assert error.value.code is code
    assert str(error.value) == code.value
    assert "{" not in str(error.value)


@pytest.mark.parametrize("plaintext", [b"", b"abc\0def", bytes(range(256))])
def test_exact_binary_round_trip(plaintext: bytes) -> None:
    key = StorageKey(1, KEY_BYTES)
    artifact_id = entity_id()
    envelope = build_envelope(
        key=key,
        artifact_id=artifact_id,
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=plaintext,
    )
    parsed = parse_envelope(envelope)
    assert len(base64.b64decode(str(parsed.header["nonce"]))) == NONCE_LENGTH
    assert decrypt_envelope(key=key, serialized=envelope)[0] == plaintext


def test_canonical_header_is_stable_and_repeated_encryption_uses_distinct_nonce() -> None:
    key = StorageKey(1, KEY_BYTES)
    artifact_id = entity_id()
    first = build_envelope(
        key=key,
        artifact_id=artifact_id,
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"same",
    )
    second = build_envelope(
        key=key,
        artifact_id=artifact_id,
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"same",
    )
    first_header, _ = _header(first)
    assert (
        canonical_header_bytes(first_header) == first[12 : 12 + struct.unpack(">I", first[8:12])[0]]
    )
    assert first_header["nonce"] != _header(second)[0]["nonce"]


def test_wrong_key_fails_authentication() -> None:
    envelope = build_envelope(
        key=StorageKey(1, KEY_BYTES),
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"secret",
    )
    with pytest.raises(StorageError) as error:
        decrypt_envelope(key=StorageKey(1, OTHER_KEY_BYTES), serialized=envelope)
    assert error.value.code is StorageErrorCode.AUTH_FAILED


@pytest.mark.parametrize(
    "mutator",
    [
        lambda e: b"BADMAGIC" + e[8:],
        lambda e: e[:12] + e[13:],
        lambda e: e + b"x",
        lambda e: e[:-TAG_LENGTH] + bytes([e[-TAG_LENGTH] ^ 1]) + e[-TAG_LENGTH + 1 :],
        lambda e: e[:-1] + bytes([e[-1] ^ 1]),
    ],
)
def test_tamper_and_trailing_bytes_fail(mutator) -> None:  # type: ignore[no-untyped-def]
    envelope = build_envelope(
        key=StorageKey(1, KEY_BYTES),
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
    )
    with pytest.raises(StorageError):
        decrypt_envelope(key=StorageKey(1, KEY_BYTES), serialized=mutator(envelope))


@pytest.mark.parametrize("cut", [0, 7, 11, 12, 20, -1, -TAG_LENGTH])
def test_truncation_fails(cut: int) -> None:
    envelope = build_envelope(
        key=StorageKey(1, KEY_BYTES),
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
    )
    data = envelope[:cut]
    with pytest.raises(StorageError):
        parse_envelope(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("algorithm", "AES-128-GCM"),
        ("format_version", 2),
        ("format_version", True),
        ("object_generation", 2),
        ("object_generation", True),
        ("key_version", 0),
        ("key_version", True),
        ("plaintext_length", -1),
        ("plaintext_length", True),
        ("plaintext_sha256", "g" * 64),
        ("plaintext_sha256", "a" * 63),
        ("artifact_id", str(uuid4()).upper()),
        ("artifact_kind", "OTHER"),
        ("nonce", "AAAA"),
        ("nonce", base64.b64encode(b"1" * NONCE_LENGTH).decode("ascii").rstrip("=")),
    ],
)
def test_invalid_header_values_fail(field: str, value: object) -> None:
    envelope = build_envelope(
        key=StorageKey(1, KEY_BYTES),
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
    )
    header, _ = _header(envelope)
    header[field] = value
    assert_storage_error(_replace_header(envelope, header))


def test_missing_extra_and_noncanonical_header_fail() -> None:
    envelope = build_envelope(
        key=StorageKey(1, KEY_BYTES),
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
    )
    header, _ = _header(envelope)
    missing = dict(header)
    del missing["nonce"]
    extra = dict(header)
    extra["extra"] = "value"
    assert_storage_error(_replace_header(envelope, missing))
    assert_storage_error(_replace_header(envelope, extra))
    assert_storage_error(_noncanonical_header(envelope, dict(reversed(header.items()))))


def test_invalid_header_length_and_oversized_header_fail() -> None:
    assert_storage_error(MAGIC + struct.pack(">I", 0) + b"" + b"x" * TAG_LENGTH)
    assert_storage_error(MAGIC + struct.pack(">I", 4097) + b"{}" + b"x" * TAG_LENGTH)


def test_key_version_mismatch_fails_context() -> None:
    envelope = build_envelope(
        key=StorageKey(1, KEY_BYTES),
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
    )
    with pytest.raises(StorageError) as error:
        decrypt_envelope(key=StorageKey(2, KEY_BYTES), serialized=envelope)
    assert error.value.code is StorageErrorCode.CONTEXT_MISMATCH
