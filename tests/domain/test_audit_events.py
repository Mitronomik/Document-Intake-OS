from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from document_intake.domain import (
    ActorKind,
    ActorRef,
    AuditAction,
    AuditEvent,
    AuditReasonCode,
    AuditSubjectType,
    AuditValueClassification,
    AuditValueSummary,
    EntityId,
    FieldKey,
    InvalidValueError,
)


def eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def actor() -> ActorRef:
    return ActorRef(eid(900), ActorKind.OPERATOR)


def event(**overrides: object) -> AuditEvent:
    values = dict(
        event_id=eid(1),
        occurred_at=datetime(2026, 7, 19, 12, tzinfo=timezone(timedelta(hours=3))),
        actor=actor(),
        action_code=AuditAction.ENTITY_CREATED,
        subject_type=AuditSubjectType.PERSON,
        subject_id=eid(2),
        field_key=FieldKey("person.sex"),
        before=None,
        after=AuditValueSummary(AuditValueClassification.NON_SENSITIVE, "CODE_1", True),
        reason_code=AuditReasonCode("OPERATOR_ACTION"),
        correlation_id=eid(3),
    )
    values.update(overrides)
    return AuditEvent(**values)  # type: ignore[arg-type]


def test_audit_enums_are_exact() -> None:
    assert tuple(AuditAction) == (
        AuditAction.ENTITY_CREATED,
        AuditAction.ENTITY_UPDATED,
        AuditAction.FIELD_CORRECTED,
        AuditAction.FIELD_VERIFIED,
        AuditAction.SNAPSHOT_CREATED,
        AuditAction.ARTIFACT_REGISTERED,
        AuditAction.EXPORT_CREATED,
        AuditAction.IMAGE_QUALITY_ASSESSED,
    )
    assert tuple(AuditSubjectType) == (
        AuditSubjectType.PERSON,
        AuditSubjectType.IDENTITY_DOCUMENT,
        AuditSubjectType.MIGRATION_DOCUMENT,
        AuditSubjectType.VEHICLE,
        AuditSubjectType.DOCUMENT,
        AuditSubjectType.FIELD_CANDIDATE,
        AuditSubjectType.APPLICATION,
        AuditSubjectType.APPLICATION_SNAPSHOT,
        AuditSubjectType.STORED_ARTIFACT,
        AuditSubjectType.IMAGE_QUALITY_ASSESSMENT,
    )
    assert tuple(AuditValueClassification) == (
        AuditValueClassification.ABSENT,
        AuditValueClassification.NON_SENSITIVE,
        AuditValueClassification.SENSITIVE_REDACTED,
    )


@pytest.mark.parametrize("value", ["A", "CODE_1", "Z9_" + "A" * 61])
def test_reason_code_accepts_controlled_codes(value: str) -> None:
    assert AuditReasonCode(value).value == value


@pytest.mark.parametrize("value", ["", " lowercase", "A B", "A-B", "1START", "A" * 65])
def test_reason_code_rejects_prose_and_unsafe_values(value: str) -> None:
    with pytest.raises(InvalidValueError):
        AuditReasonCode(value)


def test_value_summary_valid_combinations() -> None:
    assert AuditValueSummary(AuditValueClassification.ABSENT, None, False).display_value is None
    assert AuditValueSummary(AuditValueClassification.NON_SENSITIVE, "STATE:OK", True).was_present
    assert (
        AuditValueSummary(AuditValueClassification.SENSITIVE_REDACTED, None, True).display_value
        is None
    )


@pytest.mark.parametrize(
    "summary",
    [
        (AuditValueClassification.ABSENT, None, True),
        (AuditValueClassification.ABSENT, "CODE", False),
        (AuditValueClassification.NON_SENSITIVE, None, True),
        (AuditValueClassification.NON_SENSITIVE, "has space", True),
        (AuditValueClassification.NON_SENSITIVE, "A" * 65, True),
        (AuditValueClassification.NON_SENSITIVE, "CODE", False),
        (AuditValueClassification.SENSITIVE_REDACTED, "MASK", True),
        (AuditValueClassification.SENSITIVE_REDACTED, None, False),
    ],
)
def test_value_summary_rejects_invalid_combinations(
    summary: tuple[AuditValueClassification, str | None, bool],
) -> None:
    with pytest.raises(InvalidValueError):
        AuditValueSummary(*summary)


def test_audit_event_normalizes_aware_datetime_to_utc_and_reuses_actor_fieldkey() -> None:
    created = event()
    assert created.occurred_at == datetime(2026, 7, 19, 9, tzinfo=UTC)
    assert isinstance(created.actor, ActorRef)
    assert isinstance(created.field_key, FieldKey)


def test_audit_event_rejects_naive_datetime_and_invalid_types() -> None:
    with pytest.raises(InvalidValueError):
        event(occurred_at=datetime(2026, 7, 19, 12))
    with pytest.raises(InvalidValueError):
        event(action_code="ENTITY_CREATED")


def test_audit_event_is_frozen_slotted_and_safe_repr() -> None:
    created = event(
        after=AuditValueSummary(AuditValueClassification.SENSITIVE_REDACTED, None, True)
    )
    with pytest.raises(FrozenInstanceError):
        created.subject_id = eid(4)  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        created.unsafe = "value"  # type: ignore[attr-defined]
    rendered = repr(created)
    assert "SYNTH_FORBIDDEN_MARKER" not in rendered
    assert "SENSITIVE_REDACTED" not in rendered
    assert "before_present=" in rendered
