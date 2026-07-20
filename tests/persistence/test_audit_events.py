# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime
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
)
from document_intake.persistence import serialization as ser
from document_intake.persistence.database import AuditEventRepo
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.persistence.test_repositories import FakeUow, migrated_connection

FORBIDDEN = "SYNTH_FORBIDDEN_MARKER"


def eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def event(
    i: int = 1, *, occurred: datetime | None = None, correlation: EntityId | None = None
) -> AuditEvent:
    return AuditEvent(
        event_id=eid(i),
        occurred_at=occurred or datetime(2026, 7, 19, 12, i, tzinfo=UTC),
        actor=ActorRef(eid(900), ActorKind.OPERATOR),
        action_code=AuditAction.FIELD_VERIFIED,
        subject_type=AuditSubjectType.PERSON,
        subject_id=eid(100),
        field_key=FieldKey("person.sex"),
        before=AuditValueSummary(AuditValueClassification.ABSENT, None, False),
        after=AuditValueSummary(AuditValueClassification.SENSITIVE_REDACTED, None, True),
        reason_code=AuditReasonCode("OPERATOR_ACTION"),
        correlation_id=correlation,
    )


def repo() -> tuple[AuditEventRepo, FakeUow]:
    uow = FakeUow(migrated_connection())
    return AuditEventRepo(uow), uow


def test_audit_serialization_is_canonical_strict_and_pii_safe() -> None:
    payload = ser.audit_event_to_json(event())
    assert payload == ser.audit_event_to_json(ser.audit_event_from_json(payload))
    assert "SENSITIVE_REDACTED" in payload
    assert FORBIDDEN not in payload
    with pytest.raises(PersistenceError) as excinfo:
        ser.audit_event_from_json(payload[:-1])
    assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID
    with pytest.raises(PersistenceError):
        ser.audit_event_from_json(payload.replace('"event_id"', '"extra", "event_id"'))


def test_repository_add_get_missing_and_duplicate_are_sanitized() -> None:
    r, _ = repo()
    e = event()
    r.add(e)
    assert r.get(e.event_id) == e
    assert r.get(eid(404)) is None
    with pytest.raises(PersistenceError) as dup:
        r.add(e)
    assert dup.value.code == PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    assert "audit_events" not in str(dup.value)


def test_subject_and_correlation_lists_are_deterministically_ordered() -> None:
    r, _ = repo()
    corr = eid(700)
    later = event(9, occurred=datetime(2026, 7, 19, 12, 1, tzinfo=UTC), correlation=corr)
    first_b = event(3, occurred=datetime(2026, 7, 19, 12, 0, tzinfo=UTC), correlation=corr)
    first_a = event(2, occurred=datetime(2026, 7, 19, 12, 0, tzinfo=UTC), correlation=corr)
    for e in (later, first_b, first_a):
        r.add(e)
    assert r.list_for_subject(AuditSubjectType.PERSON, eid(100)) == (first_a, first_b, later)
    assert r.list_by_correlation(corr) == (first_a, first_b, later)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_events SET action_code='ENTITY_UPDATED' WHERE event_id=?",
        "DELETE FROM audit_events WHERE event_id=?",
        "INSERT OR REPLACE INTO audit_events(event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type, subject_id, payload) VALUES (?, '2026-07-19T00:00:00Z', ?, 'SYSTEM', 'ENTITY_CREATED', 'PERSON', ?, '{}')",
        "REPLACE INTO audit_events(event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type, subject_id, payload) VALUES (?, '2026-07-19T00:00:00Z', ?, 'SYSTEM', 'ENTITY_CREATED', 'PERSON', ?, '{}')",
    ],
)
def test_database_rejects_update_delete_and_replacement_forms(sql: str) -> None:
    r, _uow = repo()
    e = event()
    r.add(e)
    params = (
        (str(e.event_id),)
        if sql.startswith(("UPDATE", "DELETE"))
        else (str(e.event_id), str(e.actor.actor_id), str(e.subject_id))
    )
    with pytest.raises(PersistenceError) as excinfo:
        r._execute(sql, params)
    assert excinfo.value.code in {
        PersistenceErrorCode.PERSISTENCE_CONSTRAINT,
        PersistenceErrorCode.ENTITY_ALREADY_EXISTS,
    }
    assert r.get(e.event_id) == e


def test_projection_and_payload_tamper_fail_closed() -> None:
    r, uow = repo()
    e = event()
    r.add(e)
    uow.conn.execute("PRAGMA recursive_triggers=OFF")
    uow.conn.execute("DROP TRIGGER audit_events_no_update")
    uow.conn.execute(
        "UPDATE audit_events SET subject_id=? WHERE event_id=?", (str(eid(999)), str(e.event_id))
    )
    with pytest.raises(PersistenceError) as excinfo:
        r.get(e.event_id)
    assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_malformed_persisted_payload_fails_closed_without_payload_leak() -> None:
    r, uow = repo()
    e = event()
    columns = ser.audit_event_columns(e)
    uow.conn.execute(
        "INSERT INTO audit_events(event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type, subject_id, field_key, before_classification, before_was_present, before_display_value, after_classification, after_was_present, after_display_value, reason_code, correlation_id, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (*columns, "{not-json-" + FORBIDDEN),
    )
    with pytest.raises(PersistenceError) as excinfo:
        r.get(e.event_id)
    assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID
    assert FORBIDDEN not in str(excinfo.value)


def test_list_for_subject_validates_tampered_rows_before_filtering() -> None:
    r, uow = repo()
    e = event(10, correlation=eid(701))
    r.add(e)
    uow.conn.execute("DROP TRIGGER audit_events_no_update")
    uow.conn.execute(
        "UPDATE audit_events SET subject_id=? WHERE event_id=?",
        (str(eid(999)), str(e.event_id)),
    )
    with pytest.raises(PersistenceError) as excinfo:
        r.list_for_subject(AuditSubjectType.PERSON, eid(100))
    assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_list_by_correlation_validates_tampered_rows_before_filtering() -> None:
    r, uow = repo()
    corr = eid(702)
    e = event(11, correlation=corr)
    r.add(e)
    uow.conn.execute("DROP TRIGGER audit_events_no_update")
    uow.conn.execute(
        "UPDATE audit_events SET correlation_id=? WHERE event_id=?",
        (str(eid(999)), str(e.event_id)),
    )
    with pytest.raises(PersistenceError) as excinfo:
        r.list_by_correlation(corr)
    assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID
