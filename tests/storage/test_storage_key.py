from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.storage import StorageKey
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.storage.errors import StorageError, StorageErrorCode
from document_intake.storage.filesystem import ImmutableFilesystemStorage

from .conftest import StaticKeyProvider, WrongVersionProvider, aware_now, entity_id

VALID_DIGEST = "0" * 64


@pytest.mark.parametrize("version", [True, 0, -1, "1"])
def test_storage_key_rejects_invalid_version(version: object) -> None:
    with pytest.raises(ValueError):
        StorageKey(version, b"k" * 32)  # type: ignore[arg-type]


@pytest.mark.parametrize("key_bytes", [b"short", "not-bytes", bytearray(b"k" * 32)])
def test_storage_key_rejects_invalid_key_material(key_bytes: object) -> None:
    with pytest.raises(ValueError):
        StorageKey(1, key_bytes)  # type: ignore[arg-type]


def test_storage_key_repr_redacts_key_bytes() -> None:
    assert "kkkk" not in repr(StorageKey(1, b"k" * 32))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_id", uuid4()),
        ("artifact_kind", "ORIGINAL"),
        ("object_generation", True),
        ("object_generation", 2),
        ("plaintext_length", True),
        ("plaintext_length", -1),
        ("plaintext_sha256", "g" * 64),
        ("ciphertext_sha256", "A" * 64),
        ("key_version", True),
        ("key_version", 0),
        ("storage_format_version", True),
        ("storage_format_version", 2),
        ("created_at", datetime.now()),
    ],
)
def test_stored_artifact_record_rejects_invalid_invariants(field: str, value: object) -> None:
    kwargs = {
        "artifact_id": EntityId(uuid4()),
        "artifact_kind": ArtifactKind.ORIGINAL,
        "object_generation": 1,
        "plaintext_length": 0,
        "plaintext_sha256": VALID_DIGEST,
        "ciphertext_sha256": VALID_DIGEST,
        "key_version": 1,
        "storage_format_version": 1,
        "created_at": datetime.now(UTC),
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        StoredArtifactRecord(**kwargs)  # type: ignore[arg-type]


def test_provider_key_version_mismatch_fails_closed(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"bytes",
        created_at=aware_now(),
    )
    mismatched = ImmutableFilesystemStorage(tmp_path, WrongVersionProvider())
    with pytest.raises(StorageError) as error:
        mismatched.read_bytes(expected=record)
    assert error.value.code is StorageErrorCode.KEY_VERSION_INVALID


def test_record_repr_redacts_digests() -> None:
    record = StoredArtifactRecord(
        artifact_id=EntityId(uuid4()),
        artifact_kind=ArtifactKind.ORIGINAL,
        object_generation=1,
        plaintext_length=0,
        plaintext_sha256=VALID_DIGEST,
        ciphertext_sha256="1" * 64,
        key_version=1,
        storage_format_version=1,
        created_at=datetime.now(UTC),
    )
    assert VALID_DIGEST not in repr(record)
    assert replace(record, plaintext_length=0) == record
