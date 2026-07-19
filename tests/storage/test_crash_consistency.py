from __future__ import annotations

import pytest

from document_intake.domain.enums import ArtifactKind
from document_intake.storage.errors import StorageError
from document_intake.storage.filesystem import (
    FilesystemFailurePoint,
    ImmutableFilesystemStorage,
    _FailingFilesystemOperations,
)

from .conftest import StaticKeyProvider, aware_now, entity_id
from .test_filesystem_publication import object_path


@pytest.mark.parametrize("point", tuple(FilesystemFailurePoint))
def test_deterministic_publication_failure_points_leave_no_plaintext(tmp_path, point) -> None:
    ops = _FailingFilesystemOperations(point)
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider(), filesystem_operations=ops)
    artifact_id = entity_id()
    plaintext = b"synthetic plaintext marker"
    with pytest.raises(StorageError):
        storage.publish_bytes(
            artifact_id=artifact_id,
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=plaintext,
            created_at=aware_now(),
        )
    final = object_path(tmp_path, artifact_id)
    if point in {
        FilesystemFailurePoint.AFTER_FINAL_PUBLICATION,
        FilesystemFailurePoint.DURING_DIRECTORY_FSYNC,
    }:
        assert final.exists()
        assert storage.reconcile(expected=()).counts["orphan"] == 1
    else:
        assert not final.exists()
    for file in tmp_path.rglob("*"):
        if file.is_file() and not file.is_symlink():
            assert plaintext not in file.read_bytes()


def test_existing_valid_object_unchanged_after_failure(tmp_path) -> None:
    baseline = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = baseline.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"baseline",
        created_at=aware_now(),
    )
    final = object_path(tmp_path, record.artifact_id)
    before = final.read_bytes()
    failing = ImmutableFilesystemStorage(
        tmp_path,
        StaticKeyProvider(),
        filesystem_operations=_FailingFilesystemOperations(
            FilesystemFailurePoint.BEFORE_FINAL_PUBLICATION
        ),
    )
    with pytest.raises(StorageError):
        failing.publish_bytes(
            artifact_id=entity_id(),
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=b"new payload",
            created_at=aware_now(),
        )
    assert final.read_bytes() == before
