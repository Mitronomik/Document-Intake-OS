from __future__ import annotations

import pytest

from document_intake.domain.enums import ArtifactKind
from document_intake.storage.errors import StorageError, StorageErrorCode
from document_intake.storage.filesystem import ImmutableFilesystemStorage, _FilesystemOperations

from .conftest import StaticKeyProvider, aware_now, entity_id
from .test_filesystem_publication import object_path


def test_cleanup_removes_only_exact_regular_temporary_files(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    directory = object_path(tmp_path, record.artifact_id).parent
    exact = directory / ".tmp-00000000-0000-0000-0000-000000000000.diosobj"
    near = directory / ".tmp-not-a-uuid.diosobj"
    unknown = directory / "unknown.bin"
    temp_dir = directory / ".tmp-11111111-1111-1111-1111-111111111111.diosobj"
    exact.write_bytes(b"encrypted")
    near.write_bytes(b"keep")
    unknown.write_bytes(b"keep")
    temp_dir.mkdir()
    assert storage.cleanup_temporary_files() == 1
    assert not exact.exists()
    assert near.exists()
    assert unknown.exists()
    assert temp_dir.is_dir()
    assert object_path(tmp_path, record.artifact_id).exists()


class CleanupFailingOps(_FilesystemOperations):
    def unlink(self, path):  # type: ignore[no-untyped-def]
        raise OSError


def test_cleanup_failure_is_sanitized(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(
        tmp_path, StaticKeyProvider(), filesystem_operations=CleanupFailingOps()
    )
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    directory = object_path(tmp_path, record.artifact_id).parent
    (directory / ".tmp-00000000-0000-0000-0000-000000000000.diosobj").write_bytes(b"encrypted")
    with pytest.raises(StorageError) as error:
        storage.cleanup_temporary_files()
    assert error.value.code is StorageErrorCode.TEMP_CLEANUP_FAILED
