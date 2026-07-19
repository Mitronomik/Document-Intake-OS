"""Narrow PR-006 storage publication command."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.persistence import UnitOfWork
from document_intake.application.ports.storage import StoragePort
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId


class ArtifactRegistrationFailurePoint(StrEnum):
    BEFORE_DB_REGISTRATION = "before_db_registration"
    DURING_REPOSITORY_ADD = "during_repository_add"
    DURING_COMMIT = "during_commit"
    AFTER_EXPLICIT_ROLLBACK = "after_explicit_rollback"
    AFTER_UNCOMMITTED_EXIT = "after_uncommitted_exit"


@dataclass(frozen=True, slots=True)
class ArtifactRegistrationFault(Exception):
    failure_point: ArtifactRegistrationFailurePoint

    def __str__(self) -> str:
        return self.failure_point.value


UnitOfWorkFactory = Callable[[], UnitOfWork]


def publish_and_register_artifact(
    *,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
    artifact_id: EntityId,
    artifact_kind: ArtifactKind,
    plaintext: bytes,
    created_at: datetime,
    failure_point: ArtifactRegistrationFailurePoint | None = None,
) -> StoredArtifactRecord:
    """Publish an encrypted object, then register expected state in one UoW commit."""

    record = storage.publish_bytes(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        plaintext=plaintext,
        created_at=created_at,
    )
    if failure_point is ArtifactRegistrationFailurePoint.BEFORE_DB_REGISTRATION:
        raise ArtifactRegistrationFault(failure_point)
    with unit_of_work_factory() as uow:
        if failure_point is ArtifactRegistrationFailurePoint.DURING_REPOSITORY_ADD:
            raise ArtifactRegistrationFault(failure_point)
        uow.stored_artifacts.add(record)
        if failure_point is ArtifactRegistrationFailurePoint.AFTER_EXPLICIT_ROLLBACK:
            uow.rollback()
            raise ArtifactRegistrationFault(failure_point)
        if failure_point is ArtifactRegistrationFailurePoint.AFTER_UNCOMMITTED_EXIT:
            pass
        elif failure_point is ArtifactRegistrationFailurePoint.DURING_COMMIT:
            raise ArtifactRegistrationFault(failure_point)
        else:
            uow.commit()
    if failure_point is ArtifactRegistrationFailurePoint.AFTER_UNCOMMITTED_EXIT:
        raise ArtifactRegistrationFault(failure_point)
    return record


__all__ = [
    "ArtifactRegistrationFailurePoint",
    "ArtifactRegistrationFault",
    "publish_and_register_artifact",
]
