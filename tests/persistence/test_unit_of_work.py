from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from document_intake.persistence import database
from document_intake.persistence.database import SqlCipherUnitOfWork
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.persistence.test_repositories import eid, migrated_connection, person


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
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        assert uow.persons.get(eid(1)) == person()
        with pytest.raises(PersistenceError) as nested:
            uow.__enter__()
        assert nested.value.code == PersistenceErrorCode.UOW_STATE
    with pytest.raises(PersistenceError) as closed:
        uow.persons.list_all()
    assert closed.value.code == PersistenceErrorCode.UOW_CLOSED

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


def test_uow_does_not_apply_pending_migrations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()
    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    with pytest.raises(PersistenceError) as excinfo, SqlCipherUnitOfWork(db, Provider()):
        pass
    assert excinfo.value.code == PersistenceErrorCode.SCHEMA_VERSION_UNSUPPORTED
