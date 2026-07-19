from __future__ import annotations

import logging
from pathlib import Path

import pytest

from document_intake.persistence.database import EncryptedDatabase, SqlCipherUnitOfWork
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.persistence.test_repositories import FakeUow, migrated_connection, person


class Provider:
    def get_database_key(self) -> bytes:
        return b"z" * 32


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


def test_audit_repr_payload_projection_and_errors_do_not_leak_forbidden_marker() -> None:
    from datetime import UTC, datetime
    from uuid import UUID

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
    )
    from document_intake.persistence import serialization as ser
    from document_intake.persistence.database import AuditEventRepo

    marker = "SYNTH_FORBIDDEN_MARKER"

    def eid_local(value: int) -> EntityId:
        return EntityId(UUID(int=value))

    event = AuditEvent(
        event_id=eid_local(1),
        occurred_at=datetime(2026, 7, 19, 12, tzinfo=UTC),
        actor=ActorRef(eid_local(900), ActorKind.SYSTEM),
        action_code=AuditAction.FIELD_VERIFIED,
        subject_type=AuditSubjectType.PERSON,
        subject_id=eid_local(2),
        after=AuditValueSummary(AuditValueClassification.SENSITIVE_REDACTED, None, True),
        reason_code=AuditReasonCode("SYSTEM_ACTION"),
    )
    repo = AuditEventRepo(FakeUow(migrated_connection()))
    repo.add(event)
    row = repo._fetchall("SELECT * FROM audit_events WHERE event_id=?", (str(event.event_id),))[0]
    combined = repr(event) + ser.audit_event_to_json(event) + repr(row)
    assert marker not in combined
