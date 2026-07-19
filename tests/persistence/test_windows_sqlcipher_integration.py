from __future__ import annotations

import importlib.metadata
import platform
import sqlite3
from pathlib import Path

import pytest

from document_intake.domain import NonEmptyText, Person
from document_intake.persistence import APPLICATION_ID, CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.persistence.test_repositories import eid

pytestmark = pytest.mark.skipif(
    not (platform.system() == "Windows" and platform.machine() == "AMD64"),
    reason="actual sqlcipher3 integration runs only on Windows AMD64",
)


class Provider:
    def __init__(self, key: bytes) -> None:
        self.key = key

    def get_database_key(self) -> bytes:
        return self.key


def create_multi_page_database(path: Path, key: bytes) -> EncryptedDatabase:
    database = EncryptedDatabase(path, Provider(key))
    database.initialize()
    with database.unit_of_work() as uow:
        for index in range(600):
            uow.persons.add(
                Person(
                    eid(1000 + index),
                    full_name_latin=NonEmptyText(
                        f"Tamper Synthetic Identity {index:04d} " + "X" * 192
                    ),
                )
            )
        connection = uow._connection()
        uow.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    assert path.stat().st_size > 4 * 4096
    return database


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
        connection = uow._connection()

        cipher_version_row = connection.execute("PRAGMA cipher_version").fetchone()
        assert cipher_version_row is not None
        assert isinstance(cipher_version_row[0], str)
        assert cipher_version_row[0].strip()

        cipher_status_row = connection.execute("PRAGMA cipher_status").fetchone()
        assert cipher_status_row is not None

        cipher_status = cipher_status_row[0]
        status_is_active = (
            (
                isinstance(cipher_status, int)
                and not isinstance(cipher_status, bool)
                and cipher_status == 1
            )
            or (isinstance(cipher_status, str) and cipher_status == "1")
            or (isinstance(cipher_status, bytes) and cipher_status == b"1")
        )

        assert status_is_active, (
            "Unexpected cipher_status representation: "
            f"type={type(cipher_status).__name__}, value={cipher_status!r}"
        )

        assert connection.execute("SELECT count(*) FROM sqlite_master").fetchone() is not None

        assert connection.execute("PRAGMA cipher_integrity_check").fetchall() == []
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

    captured = capsys.readouterr()
    output = captured.out + captured.err + caplog.text
    assert key.hex() not in output
    assert "PX000012345" not in output


def test_actual_windows_sqlcipher_ciphertext_tamper_and_truncation(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    key = b"t" * 32
    forbidden_value = "Tamper Synthetic Identity 0000"
    tampered_path = tmp_path / "tampered-synthetic.db"
    database = create_multi_page_database(tampered_path, key)

    with database.unit_of_work() as uow:
        assert uow.persons.get(eid(1000)) is not None

    ciphertext = bytearray(tampered_path.read_bytes())
    ciphertext[-128] ^= 0x01
    tampered_path.write_bytes(ciphertext)
    with pytest.raises(PersistenceError) as tampered, database.unit_of_work():
        pass
    assert tampered.value.code == PersistenceErrorCode.DB_INTEGRITY_FAILED

    truncated_path = tmp_path / "truncated-synthetic.db"
    truncated_database = create_multi_page_database(truncated_path, key)
    truncated_ciphertext = truncated_path.read_bytes()
    truncated_path.write_bytes(truncated_ciphertext[:-4096])
    with pytest.raises(PersistenceError) as truncated, truncated_database.unit_of_work():
        pass
    assert truncated.value.code in {
        PersistenceErrorCode.DB_KEY_REJECTED,
        PersistenceErrorCode.DB_INTEGRITY_FAILED,
    }

    captured = capsys.readouterr()
    combined = "\n".join(
        (
            captured.out,
            captured.err,
            caplog.text,
            str(tampered.value),
            str(truncated.value),
        )
    )
    for forbidden in (
        key.hex(),
        str(tampered_path),
        str(truncated_path),
        forbidden_value,
    ):
        assert forbidden not in combined
