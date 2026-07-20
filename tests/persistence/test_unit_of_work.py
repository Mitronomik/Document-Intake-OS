from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from document_intake.persistence import database
from document_intake.persistence.database import SqlCipherUnitOfWork
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.persistence.test_repositories import actor, document, eid, migrated_connection, person


class Provider:
    def get_database_key(self) -> bytes:
        return b"k" * 32


def migrated_file(path: Path) -> None:
    source = migrated_connection()
    target = sqlite3.connect(path, isolation_level=None)
    source.backup(target)
    target.close()
    source.close()


def open_sqlite(path: Path, provider: Provider) -> sqlite3.Connection:
    return sqlite3.connect(path, isolation_level=None)


def test_uow_commit_rollback_exception_and_closed_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "synthetic.db"
    migrated_file(db)
    monkeypatch.setattr(database, "_open_connection", open_sqlite)

    with SqlCipherUnitOfWork(db, Provider()) as uow:
        uow.persons.add(person())
        uow.commit()
        for operation in (uow.commit, uow.rollback, lambda: uow.persons.list_all()):
            with pytest.raises(PersistenceError) as terminal:
                operation()
            assert terminal.value.code == PersistenceErrorCode.UOW_STATE
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        assert uow.persons.get(eid(1)) == person()
        with pytest.raises(PersistenceError) as nested:
            uow.__enter__()
        assert nested.value.code == PersistenceErrorCode.UOW_STATE
    with pytest.raises(PersistenceError) as closed:
        uow.persons.list_all()
    assert closed.value.code == PersistenceErrorCode.UOW_CLOSED

    explicit_rollback = SqlCipherUnitOfWork(db, Provider())
    with explicit_rollback:
        explicit_rollback.rollback()
        for operation in (
            explicit_rollback.commit,
            explicit_rollback.rollback,
            lambda: explicit_rollback.persons.list_all(),
        ):
            with pytest.raises(PersistenceError) as terminal:
                operation()
            assert terminal.value.code == PersistenceErrorCode.UOW_STATE
    with pytest.raises(PersistenceError) as rollback_closed:
        explicit_rollback.rollback()
    assert rollback_closed.value.code == PersistenceErrorCode.UOW_CLOSED

    with SqlCipherUnitOfWork(db, Provider()) as rollback_uow:
        rollback_uow.persons.add(
            person().__class__(eid(2), full_name_latin=person().full_name_latin)
        )
    with SqlCipherUnitOfWork(db, Provider()) as verify:
        assert verify.persons.get(eid(2)) is None

    with pytest.raises(RuntimeError), SqlCipherUnitOfWork(db, Provider()) as exception_uow:
        exception_uow.persons.add(
            person().__class__(eid(3), full_name_latin=person().full_name_latin)
        )
        raise RuntimeError("safe synthetic failure")
    with SqlCipherUnitOfWork(db, Provider()) as verify:
        assert verify.persons.get(eid(1)) == person()
        assert verify.persons.get(eid(3)) is None

    with pytest.raises(PersistenceError) as commit_after_close:
        uow.commit()
    assert commit_after_close.value.code == PersistenceErrorCode.UOW_CLOSED


class TrackingConnection:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        fail_begin: bool = False,
        fail_commit: bool = False,
        fail_rollback: bool = False,
    ) -> None:
        self.connection = connection
        self.fail_begin = fail_begin
        self.fail_commit = fail_commit
        self.fail_rollback = fail_rollback
        self.closed = False
        self.rolled_back = False

    @property
    def in_transaction(self) -> bool:
        return self.connection.in_transaction

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
        if self.fail_begin and sql == "BEGIN IMMEDIATE":
            raise sqlite3.OperationalError("synthetic begin failure")
        if self.fail_commit and sql == "COMMIT":
            raise sqlite3.OperationalError("synthetic commit failure")
        if self.fail_rollback and sql == "ROLLBACK":
            raise sqlite3.OperationalError("synthetic rollback failure")
        if sql == "ROLLBACK":
            self.rolled_back = True
        return self.connection.execute(sql, parameters)

    def close(self) -> None:
        self.closed = True
        self.connection.close()


def test_uow_failed_schema_validation_closes_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = TrackingConnection(migrated_connection())
    monkeypatch.setattr(database, "_open_connection", lambda path, provider: tracked)

    def fail_schema(connection: object) -> None:
        _ = connection
        raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)

    monkeypatch.setattr(database, "_validate_schema", fail_schema)
    uow = SqlCipherUnitOfWork(tmp_path / "synthetic.db", Provider())
    with pytest.raises(PersistenceError) as excinfo:
        uow.__enter__()
    assert excinfo.value.code == PersistenceErrorCode.SCHEMA_HISTORY_INVALID
    assert tracked.closed
    with pytest.raises(PersistenceError) as closed:
        uow.__enter__()
    assert closed.value.code == PersistenceErrorCode.UOW_CLOSED


def test_uow_failed_begin_closes_connection_and_normalizes_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = TrackingConnection(migrated_connection(), fail_begin=True)
    monkeypatch.setattr(database, "_open_connection", lambda path, provider: tracked)
    uow = SqlCipherUnitOfWork(tmp_path / "synthetic.db", Provider())
    with pytest.raises(PersistenceError) as excinfo:
        uow.__enter__()
    assert excinfo.value.code == PersistenceErrorCode.PERSISTENCE_UNEXPECTED
    assert tracked.closed


def test_uow_failed_repository_construction_rolls_back_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = TrackingConnection(migrated_connection())
    monkeypatch.setattr(database, "_open_connection", lambda path, provider: tracked)

    def fail_repositories(uow: SqlCipherUnitOfWork) -> None:
        _ = uow
        raise RuntimeError("synthetic repository construction failure")

    monkeypatch.setattr(SqlCipherUnitOfWork, "_construct_repositories", fail_repositories)
    uow = SqlCipherUnitOfWork(tmp_path / "synthetic.db", Provider())
    with pytest.raises(PersistenceError) as excinfo:
        uow.__enter__()
    assert excinfo.value.code == PersistenceErrorCode.PERSISTENCE_UNEXPECTED
    assert tracked.rolled_back
    assert tracked.closed


@pytest.mark.parametrize("operation", ["commit", "rollback"])
def test_uow_terminal_driver_failure_invalidates_and_closes(
    operation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracked = TrackingConnection(
        migrated_connection(),
        fail_commit=operation == "commit",
        fail_rollback=operation == "rollback",
    )
    monkeypatch.setattr(database, "_open_connection", lambda path, provider: tracked)
    uow = SqlCipherUnitOfWork(tmp_path / "synthetic.db", Provider())
    uow.__enter__()
    uow.persons.add(person())

    with pytest.raises(PersistenceError) as failure:
        getattr(uow, operation)()
    assert failure.value.code == PersistenceErrorCode.PERSISTENCE_UNEXPECTED
    assert "synthetic" not in str(failure.value)
    assert tracked.closed
    for later in (lambda: uow.persons.list_all(), uow.commit, uow.rollback):
        with pytest.raises(PersistenceError) as closed:
            later()
        assert closed.value.code == PersistenceErrorCode.UOW_CLOSED


def test_raise_rollback_invalidates_uow_and_prevents_later_autocommit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "raise-rollback.db"
    migrated_file(db)
    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    with SqlCipherUnitOfWork(db, Provider()) as seed:
        seed.persons.add(person())
        seed.commit()

    failing = SqlCipherUnitOfWork(db, Provider())
    with failing:
        failing.persons.add(person().__class__(eid(2), full_name_latin=person().full_name_latin))
        stale_persons = failing.persons
        failing._connection().execute(
            "CREATE TRIGGER synthetic_outer_rollback BEFORE INSERT ON document_sides "
            "BEGIN SELECT RAISE(ROLLBACK, 'synthetic outer rollback'); END"
        )
        with pytest.raises(PersistenceError) as failure:
            failing.documents.add(document())
        assert failure.value.code == PersistenceErrorCode.PERSISTENCE_UNEXPECTED
        assert "synthetic outer rollback" not in str(failure.value)
        for later in (
            lambda: stale_persons.add(
                person().__class__(eid(3), full_name_latin=person().full_name_latin)
            ),
            failing.commit,
            failing.rollback,
        ):
            with pytest.raises(PersistenceError) as closed:
                later()
            assert closed.value.code == PersistenceErrorCode.UOW_CLOSED

    with SqlCipherUnitOfWork(db, Provider()) as verify:
        assert verify.persons.get(eid(2)) is None
        assert verify.persons.get(eid(3)) is None
        assert verify.documents.get(eid(40)) is None
        assert (
            verify._connection()
            .execute(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type='trigger' AND name='synthetic_outer_rollback'"
            )
            .fetchone()[0]
            == 0
        )


def test_uow_does_not_apply_pending_migrations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()
    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    with pytest.raises(PersistenceError) as excinfo, SqlCipherUnitOfWork(db, Provider()):
        pass
    assert excinfo.value.code == PersistenceErrorCode.SCHEMA_VERSION_UNSUPPORTED


def audit_event_for_uow() -> object:
    from datetime import UTC, datetime

    from document_intake.domain import (
        AuditAction,
        AuditEvent,
        AuditReasonCode,
        AuditSubjectType,
        AuditValueClassification,
        AuditValueSummary,
    )

    return AuditEvent(
        event_id=eid(700),
        occurred_at=datetime(2026, 7, 19, 12, tzinfo=UTC),
        actor=actor(),
        action_code=AuditAction.ENTITY_CREATED,
        subject_type=AuditSubjectType.PERSON,
        subject_id=eid(701),
        after=AuditValueSummary(AuditValueClassification.SENSITIVE_REDACTED, None, True),
        reason_code=AuditReasonCode("SYSTEM_ACTION"),
        correlation_id=eid(702),
    )


def test_uow_commits_and_rolls_back_business_write_with_audit_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "synthetic-audit.db"
    migrated_file(db)
    monkeypatch.setattr(database, "_open_connection", open_sqlite)

    with SqlCipherUnitOfWork(db, Provider()) as uow:
        uow.persons.add(person().__class__(eid(701), full_name_latin=person().full_name_latin))
        uow.audit_events.add(audit_event_for_uow())
        uow.commit()
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        assert uow.persons.get(eid(701)) is not None
        assert uow.audit_events.get(eid(700)) is not None

    with SqlCipherUnitOfWork(db, Provider()) as uow:
        uow.persons.add(person().__class__(eid(702), full_name_latin=person().full_name_latin))
        from dataclasses import replace

        uow.audit_events.add(replace(audit_event_for_uow(), event_id=eid(703), subject_id=eid(702)))
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        assert uow.persons.get(eid(702)) is None
        assert uow.audit_events.get(eid(703)) is None


def test_audit_repository_after_uow_close_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "synthetic-audit-closed.db"
    migrated_file(db)
    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        audit_repo = uow.audit_events
    with pytest.raises(PersistenceError) as excinfo:
        audit_repo.get(eid(1))
    assert excinfo.value.code == PersistenceErrorCode.UOW_CLOSED
