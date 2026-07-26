"""PR-011 application command and byte-free result."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from document_intake.domain.errors import InvalidValueError
from document_intake.domain.prepared_jpeg import PreparedImageArtifact
from document_intake.domain.value_objects import ActorRef, EntityId


@dataclass(frozen=True, slots=True)
class PrepareJpegCommand:
    prepared_artifact_id: EntityId
    stored_artifact_id: EntityId
    geometry_recipe_version_id: EntityId
    audit_event_id: EntityId
    prepared_at: datetime
    actor: ActorRef
    correlation_id: EntityId

    def __post_init__(self) -> None:
        ids = (
            self.prepared_artifact_id,
            self.stored_artifact_id,
            self.geometry_recipe_version_id,
            self.audit_event_id,
        )
        if not all(isinstance(value, EntityId) for value in ids):
            raise InvalidValueError("prepare_jpeg_command.id: invalid_type")
        record_ids = (self.prepared_artifact_id, self.stored_artifact_id, self.audit_event_id)
        if len(set(record_ids)) != len(record_ids):
            raise InvalidValueError("prepare_jpeg_command.id: identity_conflict")
        if self.prepared_at.tzinfo is None or self.prepared_at.utcoffset() != UTC.utcoffset(
            self.prepared_at
        ):
            raise InvalidValueError("prepare_jpeg_command.prepared_at: utc_required")
        if not isinstance(self.actor, ActorRef) or not isinstance(self.correlation_id, EntityId):
            raise InvalidValueError("prepare_jpeg_command.identity: invalid_type")


@dataclass(frozen=True, slots=True)
class PrepareJpegResult:
    artifact: PreparedImageArtifact
