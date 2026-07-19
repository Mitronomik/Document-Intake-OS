"""Immutable PII-safe audit event entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from document_intake.domain.enums import AuditAction, AuditSubjectType
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import (
    ActorRef,
    AuditReasonCode,
    AuditValueSummary,
    EntityId,
    FieldKey,
)


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: EntityId
    occurred_at: datetime
    actor: ActorRef
    action_code: AuditAction
    subject_type: AuditSubjectType
    subject_id: EntityId
    field_key: FieldKey | None = None
    before: AuditValueSummary | None = None
    after: AuditValueSummary | None = None
    reason_code: AuditReasonCode | None = None
    correlation_id: EntityId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, EntityId):
            raise InvalidValueError("audit_event.event_id: invalid_type")
        if not isinstance(self.occurred_at, datetime):
            raise InvalidValueError("audit_event.occurred_at: invalid_type")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise InvalidValueError("audit_event.occurred_at: timezone_aware_required")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))
        if not isinstance(self.actor, ActorRef):
            raise InvalidValueError("audit_event.actor: invalid_type")
        if not isinstance(self.action_code, AuditAction):
            raise InvalidValueError("audit_event.action_code: invalid_type")
        if not isinstance(self.subject_type, AuditSubjectType):
            raise InvalidValueError("audit_event.subject_type: invalid_type")
        if not isinstance(self.subject_id, EntityId):
            raise InvalidValueError("audit_event.subject_id: invalid_type")
        if self.field_key is not None and not isinstance(self.field_key, FieldKey):
            raise InvalidValueError("audit_event.field_key: invalid_type")
        if self.before is not None and not isinstance(self.before, AuditValueSummary):
            raise InvalidValueError("audit_event.before: invalid_type")
        if self.after is not None and not isinstance(self.after, AuditValueSummary):
            raise InvalidValueError("audit_event.after: invalid_type")
        if self.reason_code is not None and not isinstance(self.reason_code, AuditReasonCode):
            raise InvalidValueError("audit_event.reason_code: invalid_type")
        if self.correlation_id is not None and not isinstance(self.correlation_id, EntityId):
            raise InvalidValueError("audit_event.correlation_id: invalid_type")

    def __repr__(self) -> str:
        return (
            "AuditEvent("
            f"event_id={self.event_id}, action_code={self.action_code.value}, "
            f"subject_type={self.subject_type.value}, subject_id={self.subject_id}, "
            f"field_key_present={self.field_key is not None}, "
            f"before_present={self.before is not None}, after_present={self.after is not None}, "
            f"reason_code_present={self.reason_code is not None}, "
            f"correlation_id_present={self.correlation_id is not None})"
        )
