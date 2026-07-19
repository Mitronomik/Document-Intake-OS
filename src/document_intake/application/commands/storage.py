"""Narrow PR-006 storage publication command."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.persistence import UnitOfWork
from document_intake.application.ports.storage import StoragePort
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId

UnitOfWorkFactory = Callable[[], UnitOfWork]


def publish_and_register_artifact(
    *,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
    artifact_id: EntityId,
    artifact_kind: ArtifactKind,
    plaintext: bytes,
    created_at: datetime,
) -> StoredArtifactRecord:
    """Publish an encrypted object, then register expected state in one UoW commit."""

    record = storage.publish_bytes(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        plaintext=plaintext,
        created_at=created_at,
    )
    with unit_of_work_factory() as uow:
        uow.stored_artifacts.add(record)
        uow.commit()
    return record


__all__ = [
    "publish_and_register_artifact",
]
