from __future__ import annotations

import importlib.metadata
import platform
import sqlite3
from pathlib import Path

import pytest
from tests.persistence.test_repositories import eid

from document_intake.domain import NonEmptyText, Person
from document_intake.persistence import APPLICATION_ID, CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode

pytestmark = pytest.mark.skipif(
    not (platform.system() == "Windows" and platform.machine() == "AMD64"),
    reason="actual sqlcipher3 integration runs only on Windows AMD64",
)


class Provider:
    def __init__(self, key: bytes) -> None:
        self.key = key

    def get_database_key(self) -> bytes:
        return self.key


def test_actual_windows_sqlcipher_encryption_uow_and_privacy(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    assert importlib.metadata.version("sqlcipher3") == "0.6.2"

    key = b"w" * 32
    wrong = b"x" * 32
    db_path = tmp_path / "synthetic.db"
    db = EncryptedDatabase(db_path, Provider(key))
    db.initialize()
    assert db_path.read_bytes()[:16] != b"SQLite format 3\x00"
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(db_path).execute("SELECT count(*) FROM schema_migrations").fetchone()

    with db.unit_of_work() as uow:
        uow.persons.add(Person(eid(1), full_name_latin=NonEmptyText("Windows Synthetic")))
        uow.commit()
    with db.unit_of_work() as uow:
        assert uow.persons.get(eid(1)) is not None
        assert uow._connection().execute("PRAGMA cipher_status").fetchone()[0] == "active"
        assert (
            uow._connection().execute("PRAGMA cipher_integrity_check").fetchall()[0][0].lower()
            == "ok"
        )
        assert uow._connection().execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert uow._connection().execute("PRAGMA temp_store").fetchone()[0] == 2
        assert uow._connection().execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert uow._connection().execute("PRAGMA synchronous").fetchone()[0] == 2
        assert uow._connection().execute("PRAGMA trusted_schema").fetchone()[0] == 0
        assert (
            uow._connection().execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
        )
        assert uow._connection().execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
    with (
        pytest.raises(PersistenceError) as wrong_key,
        EncryptedDatabase(db_path, Provider(wrong)).unit_of_work(),
    ):
        pass
    assert wrong_key.value.code == PersistenceErrorCode.DB_KEY_REJECTED
    with db.unit_of_work() as uow:
        uow.persons.add(Person(eid(2), full_name_latin=NonEmptyText("Rollback Synthetic")))
    with db.unit_of_work() as uow:
        assert uow.persons.get(eid(2)) is None

    output = capsys.readouterr().out + capsys.readouterr().err + caplog.text
    assert key.hex() not in output
    assert "PX000012345" not in output
