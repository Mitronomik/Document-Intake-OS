from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from document_intake.domain.enums import ArtifactKind
from document_intake.storage.errors import StorageError, StorageErrorCode
from document_intake.storage.filesystem import ImmutableFilesystemStorage

from .conftest import StaticKeyProvider, aware_now, entity_id


def object_path(root, artifact_id):  # type: ignore[no-untyped-def]
    uuid_hex = artifact_id.value.hex
    return root / "objects" / uuid_hex[:2] / uuid_hex[2:4] / f"{artifact_id}.diosobj"


def test_uuid_only_path_and_no_plaintext(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    artifact_id = entity_id()
    plaintext = b"synthetic source filename passport vin marker"
    record = storage.publish_bytes(
        artifact_id=artifact_id,
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=plaintext,
        created_at=aware_now(),
    )
    final = object_path(tmp_path, artifact_id)
    assert final.exists()
    assert final.name == f"{artifact_id}.diosobj"
    assert plaintext not in final.read_bytes()
    assert storage.read_bytes(expected=record) == plaintext


def test_duplicate_publication_leaves_existing_object_unchanged(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    artifact_id = entity_id()
    record = storage.publish_bytes(
        artifact_id=artifact_id,
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"first",
        created_at=aware_now(),
    )
    final = object_path(tmp_path, artifact_id)
    before = final.read_bytes()
    with pytest.raises(StorageError) as error:
        storage.publish_bytes(
            artifact_id=artifact_id,
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=b"second",
            created_at=aware_now(),
        )
    assert error.value.code is StorageErrorCode.ARTIFACT_EXISTS
    assert final.read_bytes() == before
    assert storage.read_bytes(expected=record) == b"first"


@pytest.mark.parametrize(
    ("kwargs", "error_code"),
    [
        ({"artifact_id": "bad"}, StorageErrorCode.CONTEXT_MISMATCH),
        ({"artifact_kind": "ORIGINAL"}, StorageErrorCode.CONTEXT_MISMATCH),
        ({"plaintext": bytearray(b"x")}, StorageErrorCode.CONTEXT_MISMATCH),
        ({"created_at": datetime.now()}, StorageErrorCode.CONTEXT_MISMATCH),
    ],
)
def test_invalid_publish_input_writes_nothing(
    tmp_path, kwargs: dict[str, object], error_code
) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    values: dict[str, object] = {
        "artifact_id": entity_id(),
        "artifact_kind": ArtifactKind.ORIGINAL,
        "plaintext": b"payload",
        "created_at": aware_now(),
    }
    values.update(kwargs)
    with pytest.raises(StorageError) as error:
        storage.publish_bytes(**values)  # type: ignore[arg-type]
    assert error.value.code is error_code
    assert list((tmp_path / "objects").iterdir()) == []


def test_invalid_provider_return_writes_nothing(tmp_path) -> None:
    class BadProvider:
        def get_current_key(self) -> object:
            return b"not-a-storage-key"

        def get_key(self, version: int) -> object:
            return b"not-a-storage-key"

    storage = ImmutableFilesystemStorage(tmp_path, BadProvider())  # type: ignore[arg-type]
    with pytest.raises(StorageError) as error:
        storage.publish_bytes(
            artifact_id=entity_id(),
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=b"payload",
            created_at=aware_now(),
        )
    assert error.value.code is StorageErrorCode.KEY_INVALID
    assert list((tmp_path / "objects").iterdir()) == []


def test_expected_state_mismatches_fail(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    for invalid in (
        replace(record, ciphertext_sha256="0" * 64),
        replace(record, plaintext_sha256="0" * 64),
        replace(record, key_version=2),
        replace(record, storage_format_version=1),
    ):
        with pytest.raises(StorageError):
            storage.read_bytes(expected=invalid)


def test_missing_object_fails(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    object_path(tmp_path, record.artifact_id).unlink()
    with pytest.raises(StorageError) as error:
        storage.read_bytes(expected=record)
    assert error.value.code is StorageErrorCode.OBJECT_MISSING
