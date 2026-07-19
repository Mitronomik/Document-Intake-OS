from __future__ import annotations

from dataclasses import dataclass

import pytest

from document_intake.application.commands.storage import (
    ArtifactRegistrationFailurePoint,
    ArtifactRegistrationFault,
    publish_and_register_artifact,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain.enums import ArtifactKind
from document_intake.storage.filesystem import ImmutableFilesystemStorage

from .conftest import StaticKeyProvider, aware_now, entity_id


@dataclass
class _StoredArtifacts:
    committed: dict[str, StoredArtifactRecord]
    staged: dict[str, StoredArtifactRecord]

    def add(self, record: StoredArtifactRecord) -> None:
        self.staged[str(record.artifact_id)] = record

    def get(self, artifact_id):
        return self.committed.get(str(artifact_id))

    def list_all(self) -> tuple[StoredArtifactRecord, ...]:
        return tuple(self.committed.values())


class _UnitOfWork:
    def __init__(self, committed: dict[str, StoredArtifactRecord]) -> None:
        self.committed = committed
        self.staged: dict[str, StoredArtifactRecord] = {}
        self.stored_artifacts = _StoredArtifacts(committed, self.staged)

    def __enter__(self) -> _UnitOfWork:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None or self.staged:
            self.rollback()

    def commit(self) -> None:
        self.committed.update(self.staged)
        self.staged.clear()

    def rollback(self) -> None:
        self.staged.clear()


@pytest.mark.parametrize(
    "failure_point",
    (
        ArtifactRegistrationFailurePoint.BEFORE_DB_REGISTRATION,
        ArtifactRegistrationFailurePoint.DURING_REPOSITORY_ADD,
        ArtifactRegistrationFailurePoint.DURING_COMMIT,
        ArtifactRegistrationFailurePoint.AFTER_EXPLICIT_ROLLBACK,
        ArtifactRegistrationFailurePoint.AFTER_UNCOMMITTED_EXIT,
    ),
)
def test_publish_and_register_database_failures_leave_orphan(tmp_path, failure_point) -> None:
    committed: dict[str, StoredArtifactRecord] = {}
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())

    with pytest.raises(ArtifactRegistrationFault):
        publish_and_register_artifact(
            storage=storage,
            unit_of_work_factory=lambda: _UnitOfWork(committed),
            artifact_id=entity_id(),
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=b"registration-boundary",
            created_at=aware_now(),
            failure_point=failure_point,
        )

    assert committed == {}
    assert storage.reconcile(expected=()).counts["orphan"] == 1


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

    assert committed == {str(record.artifact_id): record}
    assert storage.reconcile(expected=tuple(committed.values())).counts == {
        "healthy": 1,
        "missing": 0,
        "invalid": 0,
        "orphan": 0,
        "temporary": 0,
    }
