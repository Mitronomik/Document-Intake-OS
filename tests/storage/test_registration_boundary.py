from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

from document_intake.application.commands.storage import publish_and_register_artifact
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain.enums import ArtifactKind
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.storage.filesystem import ImmutableFilesystemStorage

from .conftest import StaticKeyProvider, aware_now, entity_id
from .test_filesystem_publication import object_path

_MODE = Literal["success", "add_error", "commit_error", "enter_error"]


@dataclass
class _StoredArtifacts:
    committed: dict[str, StoredArtifactRecord]
    staged: dict[str, StoredArtifactRecord]
    mode: _MODE

    def add(self, record: StoredArtifactRecord) -> None:
        if self.mode == "add_error":
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)
        self.staged[str(record.artifact_id)] = record

    def get(self, artifact_id):
        return self.committed.get(str(artifact_id))

    def list_all(self) -> tuple[StoredArtifactRecord, ...]:
        return tuple(self.committed.values())


class _UnitOfWork:
    def __init__(self, committed: dict[str, StoredArtifactRecord], mode: _MODE = "success") -> None:
        self.committed = committed
        self.mode = mode
        self.staged: dict[str, StoredArtifactRecord] = {}
        self.stored_artifacts = _StoredArtifacts(committed, self.staged, mode)

    def __enter__(self) -> _UnitOfWork:
        if self.mode == "enter_error":
            raise PersistenceError(PersistenceErrorCode.DB_OPEN_FAILED)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None or self.staged:
            self.rollback()

    def commit(self) -> None:
        if self.mode == "commit_error":
            self.rollback()
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)
        self.committed.update(self.staged)
        self.staged.clear()

    def rollback(self) -> None:
        self.staged.clear()


def _assert_one_sanitized_orphan(
    *,
    tmp_path,
    storage: ImmutableFilesystemStorage,
    committed: dict[str, StoredArtifactRecord],
    artifact_id,
    plaintext: bytes,
    error: PersistenceError,
) -> None:
    assert object_path(tmp_path, artifact_id).exists()
    assert committed == {}
    assert storage.reconcile(expected=()).counts["orphan"] == 1
    for file in tmp_path.rglob("*"):
        if file.is_file() and not file.is_symlink():
            assert plaintext not in file.read_bytes()
    rendered = f"{error!s} {error!r}"
    assert str(tmp_path) not in rendered
    assert str(artifact_id) not in rendered
    assert plaintext.decode("ascii") not in rendered
    assert "stored_artifacts" not in rendered


@pytest.mark.parametrize("mode", ("enter_error", "add_error", "commit_error"))
def test_publish_and_register_database_failures_leave_detectable_orphan(
    tmp_path, mode: _MODE
) -> None:
    committed: dict[str, StoredArtifactRecord] = {}
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    artifact_id = entity_id()
    plaintext = b"registration-boundary-secret"

    with pytest.raises(PersistenceError) as captured:
        publish_and_register_artifact(
            storage=storage,
            unit_of_work_factory=lambda: _UnitOfWork(committed, mode),
            artifact_id=artifact_id,
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=plaintext,
            created_at=aware_now(),
        )

    _assert_one_sanitized_orphan(
        tmp_path=tmp_path,
        storage=storage,
        committed=committed,
        artifact_id=artifact_id,
        plaintext=plaintext,
        error=captured.value,
    )


def test_publish_and_register_success_commits_expected_record(tmp_path) -> None:
    committed: dict[str, StoredArtifactRecord] = {}
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())

    record = publish_and_register_artifact(
        storage=storage,
        unit_of_work_factory=lambda: _UnitOfWork(committed),
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"registration-success",
        created_at=aware_now(),
    )

    assert object_path(tmp_path, record.artifact_id).exists()
    assert committed == {str(record.artifact_id): record}
    assert storage.reconcile(expected=tuple(committed.values())).counts == {
        "healthy": 1,
        "missing": 0,
        "invalid": 0,
        "orphan": 0,
        "temporary": 0,
    }
