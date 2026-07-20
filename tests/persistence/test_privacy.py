from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
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
    InvalidValueError,
)
from document_intake.persistence import serialization as ser
from document_intake.persistence.database import (
    AuditEventRepo,
    EncryptedDatabase,
    SqlCipherUnitOfWork,
)
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.persistence.test_repositories import FakeUow, migrated_connection, person

FORBIDDEN_MARKER = "SYNTH FORBIDDEN MARKER"


class Provider:
    def get_database_key(self) -> bytes:
        return b"z" * 32


def eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def audit_event() -> AuditEvent:
    return AuditEvent(
        event_id=eid(1),
        occurred_at=datetime(2026, 7, 19, 12, tzinfo=UTC),
        actor=ActorRef(eid(900), ActorKind.SYSTEM),
        action_code=AuditAction.FIELD_VERIFIED,
        subject_type=AuditSubjectType.PERSON,
        subject_id=eid(2),
        after=AuditValueSummary(AuditValueClassification.SENSITIVE_REDACTED, None, True),
        reason_code=AuditReasonCode("SYSTEM_ACTION"),
    )


def test_safe_repr_errors_and_logs_do_not_leak_sensitive_values(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    db_path = tmp_path / "fictional-secret-name.db"
    key_hex = (b"z" * 32).hex()
    passport = "PX000012345"
    vin = "VIN00000000000001"
    phone = "000123456789"
    address = "Synthetic Address, Apt Quote"
    payload = "payload-secret-content"

    db = EncryptedDatabase(db_path, Provider())
    uow = SqlCipherUnitOfWork(db_path, Provider())
    repo = FakeUow(migrated_connection())
    error = PersistenceError(PersistenceErrorCode.DB_KEY_REJECTED)
    print("safe output only")
    logging.getLogger("document_intake_test").debug("safe log only")

    combined = "\n".join(
        [
            str(error),
            repr(error),
            repr(db),
            repr(uow),
            repr(repo),
            capsys.readouterr().out,
            capsys.readouterr().err,
            caplog.text,
        ]
    )
    for forbidden in (
        key_hex,
        "PRAGMA key",
        str(db_path),
        passport,
        vin,
        phone,
        address,
        payload,
        person().registration_address.value,
    ):
        assert forbidden not in combined


def test_audit_event_shape_has_no_metadata_message_or_raw_value_fields() -> None:
    assert tuple(field.name for field in fields(AuditEvent)) == (
        "event_id",
        "occurred_at",
        "actor",
        "action_code",
        "subject_type",
        "subject_id",
        "field_key",
        "before",
        "after",
        "reason_code",
        "correlation_id",
    )
    for forbidden_field in ("metadata", "message", "raw_value", "raw_values", "payload"):
        assert forbidden_field not in {field.name for field in fields(AuditEvent)}


def test_forbidden_marker_cannot_be_submitted_as_sensitive_or_controlled_value() -> None:
    with pytest.raises(InvalidValueError) as sensitive:
        AuditValueSummary(AuditValueClassification.SENSITIVE_REDACTED, FORBIDDEN_MARKER, True)
    with pytest.raises(InvalidValueError) as non_sensitive:
        AuditValueSummary(AuditValueClassification.NON_SENSITIVE, FORBIDDEN_MARKER, True)
    assert FORBIDDEN_MARKER not in str(sensitive.value)
    assert FORBIDDEN_MARKER not in str(non_sensitive.value)


def test_audit_repr_payload_projection_and_errors_do_not_leak_forbidden_marker() -> None:
    event = audit_event()
    repo = AuditEventRepo(FakeUow(migrated_connection()))
    repo.add(event)
    row = repo._fetchall("SELECT * FROM audit_events WHERE event_id=?", (str(event.event_id),))[0]
    with pytest.raises(PersistenceError) as duplicate:
        repo.add(event)
    combined = "\n".join(
        (
            repr(event),
            ser.audit_event_to_json(event),
            repr(row),
            str(duplicate.value),
            repr(duplicate.value),
        )
    )
    assert FORBIDDEN_MARKER not in combined


def test_verifier_output_does_not_leak_forbidden_marker() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_pr007_audit.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert FORBIDDEN_MARKER not in result.stdout
    assert FORBIDDEN_MARKER not in result.stderr
    assert "audit_events immutable" not in result.stdout
    assert "sqlite3.OperationalError" not in result.stdout
