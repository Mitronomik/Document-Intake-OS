"""Manual PR-007 SQLCipher audit verification with sanitized output."""
# ruff: noqa: E501

from __future__ import annotations

import importlib.util
import platform
import shutil
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
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
    NonEmptyText,
    Person,
)
from document_intake.persistence import CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations.v0003_audit_events import MIGRATION as V0003

FORBIDDEN = ("SYNTH_FORBIDDEN_MARKER", "TEMP", "sqlite3.OperationalError", "audit_events immutable")
LINES: list[str] = []


class Provider:
    def get_database_key(self) -> bytes:
        return b"a" * 32


def eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def event(value: int, *, minute: int = 0, corr: EntityId | None = None) -> AuditEvent:
    return AuditEvent(
        event_id=eid(value),
        occurred_at=datetime(2026, 7, 19, 12, minute, tzinfo=UTC),
        actor=ActorRef(eid(900), ActorKind.SYSTEM),
        action_code=AuditAction.ENTITY_CREATED,
        subject_type=AuditSubjectType.PERSON,
        subject_id=eid(100),
        before=None,
        after=AuditValueSummary(AuditValueClassification.SENSITIVE_REDACTED, None, True),
        reason_code=AuditReasonCode("SYSTEM_ACTION"),
        correlation_id=corr,
    )


def line(ok: bool, label: str) -> bool:
    text = ("PASS " if ok else "FAIL ") + label
    LINES.append(text)
    print(text)
    return ok


def expect_rejection(
    label: str,
    fn: Callable[[], object],
    expected_codes: frozenset[PersistenceErrorCode],
) -> bool:
    try:
        fn()
    except PersistenceError as error:
        return line(error.code in expected_codes, label)
    except Exception:
        return line(False, label)
    return line(False, label)


def audit_row_count(uow: Any) -> int:
    row = uow.audit_events._fetchall("SELECT count(*) FROM audit_events")
    return int(row[0][0])


def verify_rejection_preserves_event(
    label: str,
    uow: Any,
    event: AuditEvent,
    before_count: int,
) -> bool:
    return line(
        uow.audit_events.get(event.event_id) == event
        and audit_row_count(uow) == before_count
        and len(uow.audit_events.list_by_correlation(event.correlation_id)) >= 1,
        f"{label}_state_preserved",
    )


def main() -> int:
    if importlib.util.find_spec("sqlcipher3") is None:
        print("INCONCLUSIVE sqlcipher_unavailable")
        return 2
    ok = True
    temp_dir = Path(tempfile.mkdtemp(prefix="pr007-audit-"))
    try:
        db_path = temp_dir / "audit.db"
        db = EncryptedDatabase(db_path, Provider())
        db.initialize()
        ok &= line(True, f"os={platform.system()}")
        ok &= line(True, f"arch={platform.machine()}")
        ok &= line(True, f"python={platform.python_version()}")
        ok &= line(CURRENT_SCHEMA_VERSION == 6, "schema_version=6")
        ok &= line(
            V0003.checksum == "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1",
            f"v0003_checksum={V0003.checksum}",
        )
        corr = eid(700)
        with db.unit_of_work() as uow:
            e1 = event(1, minute=1, corr=corr)
            e2 = event(2, minute=0, corr=corr)
            uow.audit_events.add(e1)
            uow.audit_events.add(e2)
            ok &= line(uow.audit_events.get(e1.event_id) == e1, "audit_round_trip")
            ok &= line(
                uow.audit_events.list_for_subject(AuditSubjectType.PERSON, eid(100)) == (e2, e1),
                "subject_order",
            )
            ok &= line(uow.audit_events.list_by_correlation(corr) == (e2, e1), "correlation_order")
            before_count = audit_row_count(uow)
            constraint_codes = frozenset({PersistenceErrorCode.PERSISTENCE_CONSTRAINT})
            duplicate_codes = frozenset(
                {
                    PersistenceErrorCode.PERSISTENCE_CONSTRAINT,
                    PersistenceErrorCode.ENTITY_ALREADY_EXISTS,
                }
            )
            ok &= expect_rejection(
                "update_rejected",
                lambda: uow.audit_events._execute(
                    "UPDATE audit_events SET action_code='ENTITY_UPDATED' WHERE event_id=?",
                    (str(e1.event_id),),
                ),
                constraint_codes,
            )
            ok &= verify_rejection_preserves_event("update_rejected", uow, e1, before_count)
            ok &= expect_rejection(
                "delete_rejected",
                lambda: uow.audit_events._execute(
                    "DELETE FROM audit_events WHERE event_id=?", (str(e1.event_id),)
                ),
                constraint_codes,
            )
            ok &= verify_rejection_preserves_event("delete_rejected", uow, e1, before_count)
            ok &= expect_rejection(
                "insert_or_replace_rejected",
                lambda: uow.audit_events._execute(
                    "INSERT OR REPLACE INTO audit_events(event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type, subject_id, payload) VALUES (?, '2026-07-19T00:00:00Z', ?, 'SYSTEM', 'ENTITY_CREATED', 'PERSON', ?, '{}')",
                    (str(e1.event_id), str(e1.actor.actor_id), str(e1.subject_id)),
                    duplicate_is_already_exists=True,
                ),
                duplicate_codes,
            )
            ok &= verify_rejection_preserves_event(
                "insert_or_replace_rejected", uow, e1, before_count
            )
            ok &= expect_rejection(
                "replace_into_rejected",
                lambda: uow.audit_events._execute(
                    "REPLACE INTO audit_events(event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type, subject_id, payload) VALUES (?, '2026-07-19T00:00:00Z', ?, 'SYSTEM', 'ENTITY_CREATED', 'PERSON', ?, '{}')",
                    (str(e1.event_id), str(e1.actor.actor_id), str(e1.subject_id)),
                    duplicate_is_already_exists=True,
                ),
                duplicate_codes,
            )
            ok &= verify_rejection_preserves_event("replace_into_rejected", uow, e1, before_count)
            rows = uow.audit_events._fetchall(
                "SELECT payload, after_display_value FROM audit_events"
            )
            ok &= line(
                all("SYNTH_FORBIDDEN_MARKER" not in str(row) and row[1] is None for row in rows),
                "sensitive_redaction",
            )
            uow.commit()
        with db.unit_of_work() as uow:
            uow.persons.add(Person(eid(300), full_name_latin=NonEmptyText("Synthetic Rollback")))
            uow.audit_events.add(event(300))
        with db.unit_of_work() as uow:
            ok &= line(
                uow.persons.get(eid(300)) is None and uow.audit_events.get(eid(300)) is None,
                "rollback_atomicity",
            )
            uow.commit()
    except PersistenceError:
        ok = line(False, "persistence_error") and ok
    except Exception:
        ok = line(False, "unexpected_error") and ok
    finally:
        rendered = "\n".join(LINES)
        if any(marker in rendered for marker in FORBIDDEN):
            ok = False
            print("FAIL sanitized_output")
        shutil.rmtree(temp_dir, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
