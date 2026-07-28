from __future__ import annotations

import importlib.metadata
import platform
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from document_intake.domain import (
    AuditAction,
    AuditEvent,
    AuditReasonCode,
    AuditSubjectType,
    NonEmptyText,
    Person,
    VehicleRole,
)
from document_intake.persistence import APPLICATION_ID, CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence import database as persistence_database
from document_intake.persistence.errors import (
    PersistenceError,
    PersistenceErrorCode,
    translate_driver_error,
)
from document_intake.persistence.migrations import MIGRATIONS
from tests.persistence.test_pr011_migration_acceptance import V6_TABLES
from tests.persistence.test_repositories import (
    application,
    candidate,
    document,
    eid,
    identity_document,
    migration_document,
    person,
    snapshot,
    terminal,
    vehicle,
)
from tests.support.pr011 import (
    actor,
    correlation_id,
    entity_id,
    valid_audit_event,
    valid_geometry_recipe,
    valid_original_stored_artifact,
    valid_prepared_artifact,
    valid_prepared_stored_artifact,
    valid_quality_assessment,
    valid_source_file,
    valid_upload_batch,
)

pytestmark = pytest.mark.skipif(
    not (platform.system() == "Windows" and platform.machine() == "AMD64"),
    reason="actual sqlcipher3 integration runs only on Windows AMD64",
)


class Provider:
    def __init__(self, key: bytes) -> None:
        self.key = key

    def get_database_key(self) -> bytes:
        return self.key


def _cipher_active(connection: Any) -> None:
    version = connection.execute("PRAGMA cipher_version").fetchone()
    assert version is not None and isinstance(version[0], str) and version[0].strip()
    status = connection.execute("PRAGMA cipher_status").fetchone()
    assert status is not None and status[0] in (1, "1", b"1")


def _rows(connection: Any) -> dict[str, tuple[tuple[Any, ...], ...]]:
    return {
        table: tuple(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall())
        for table in V6_TABLES
    }


def _create_populated_encrypted_v6(
    path: Path, key: bytes, monkeypatch: pytest.MonkeyPatch
) -> dict[str, tuple[tuple[Any, ...], ...]]:
    provider = Provider(key)
    production_open_connection = persistence_database._open_connection
    connection = persistence_database._open_connection(path, provider)
    _cipher_active(connection)
    for migration in MIGRATIONS[:6]:
        persistence_database._apply_one_migration(connection, migration)
    assert connection.execute("PRAGMA user_version").fetchone() == (6,)
    assert connection.execute("PRAGMA application_id").fetchone() == (APPLICATION_ID,)
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall() == [(version,) for version in range(1, 7)]
    assert (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='prepared_image_artifacts'"
        ).fetchone()
        is None
    )
    connection.close()

    with monkeypatch.context() as v6_context:
        v6_context.setattr(persistence_database, "CURRENT_SCHEMA_VERSION", 6)
        assert persistence_database._open_connection is production_open_connection
        database = EncryptedDatabase(path, provider)
        batch = valid_upload_batch()
        source = valid_source_file()
        original = valid_original_stored_artifact()
        with database.unit_of_work() as unit:
            unit.persons.add(person())
            unit.identity_documents.add(identity_document())
            unit.migration_documents.add(migration_document())
            unit.vehicles.add(vehicle(entity_id(20), VehicleRole.TRACTOR))
            unit.vehicles.add(vehicle(entity_id(21), VehicleRole.TRAILER))
            unit.terminals.add(terminal())
            unit.documents.add(document())
            unit.field_candidates.add(candidate())
            unit.applications.add(application())
            unit.stored_artifacts.add(original)
            unit.stored_artifacts.add(replace(original, artifact_id=entity_id(81)))
            unit.stored_artifacts.add(replace(original, artifact_id=entity_id(82)))
            unit.application_snapshots.add(snapshot(application()))
            unit.upload_batches.add(batch)
            unit.source_files.add(source)
            unit.upload_batches.update(batch.append_source_file_id(source.id))
            unit.image_quality_assessments.add(valid_quality_assessment())
            unit.image_geometry_recipes.add(valid_geometry_recipe())
            unit.audit_events.add(valid_audit_event())
            unit.commit()
        with EncryptedDatabase(path, provider).unit_of_work() as reopened_unit:
            assert reopened_unit.persons.get(person().id) == person()
            assert reopened_unit.applications.get(application().id) == application()
            assert reopened_unit.source_files.get(source.id) == source
            assert reopened_unit._connection().execute("PRAGMA foreign_key_check").fetchall() == []
            assert (
                reopened_unit._connection().execute("PRAGMA cipher_integrity_check").fetchall()
                == []
            )
    assert persistence_database.CURRENT_SCHEMA_VERSION == 7
    assert persistence_database._open_connection is production_open_connection
    reopened = persistence_database._open_connection(path, provider)
    expected = _rows(reopened)
    assert all(expected[table] for table in V6_TABLES)
    assert reopened.execute("PRAGMA foreign_key_check").fetchall() == []
    assert reopened.execute("PRAGMA cipher_integrity_check").fetchall() == []
    reopened.close()
    return expected


def _migrate_encrypted_v7(path: Path, key: bytes) -> EncryptedDatabase:
    database = EncryptedDatabase(path, Provider(key))
    database.initialize()
    return database


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


def test_actual_windows_pr007_audit_verifier_sanitized_output() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/verify_pr007_audit.py"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    output = result.stdout.strip().splitlines()
    assert output
    assert all(line.startswith("PASS") for line in output)
    assert not result.stderr
    assert "SYNTH_FORBIDDEN_MARKER" not in result.stdout
    assert "sqlite3.OperationalError" not in result.stdout


def test_actual_windows_sqlcipher_schema_v7_reopens_with_clean_integrity(tmp_path: Path) -> None:
    path = tmp_path / "v7-reopen.db"
    key = b"r" * 32
    EncryptedDatabase(path, Provider(key)).initialize()
    reopened = EncryptedDatabase(path, Provider(key))
    reopened.initialize()
    with reopened.unit_of_work() as uow:
        connection = uow._connection()
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 7
        assert connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 7
        assert connection.execute("PRAGMA cipher_integrity_check").fetchall() == []
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_pr011_win_001_production_windows_sqlcipher_populated_v6_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "pr011-win-v6.db"
    key = b"v" * 32
    expected = _create_populated_encrypted_v6(path, key, monkeypatch)
    assert path.read_bytes()[:16] != b"SQLite format 3\x00"
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(path).execute("SELECT count(*) FROM schema_migrations").fetchone()
    raw = persistence_database._open_connection(path, Provider(key))
    _cipher_active(raw)
    assert raw.execute("PRAGMA user_version").fetchone() == (6,)
    assert all(expected[table] for table in V6_TABLES)
    assert raw.execute("PRAGMA foreign_key_check").fetchall() == []
    assert raw.execute("PRAGMA cipher_integrity_check").fetchall() == []
    raw.close()


def test_pr011_win_002_production_windows_sqlcipher_v6_to_v7_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "pr011-win-migration.db"
    key = b"m" * 32
    before = _create_populated_encrypted_v6(path, key, monkeypatch)
    assert persistence_database.CURRENT_SCHEMA_VERSION == 7
    _migrate_encrypted_v7(path, key)
    connection = persistence_database._open_connection(path, Provider(key))
    assert connection.execute("PRAGMA user_version").fetchone() == (7,)
    history = connection.execute(
        "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    assert history == [(m.version, m.name, m.checksum) for m in MIGRATIONS]
    assert history[-1] == (
        7,
        "prepared_jpeg_pr011",
        "afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7",
    )
    assert _rows(connection) == before
    assert connection.execute("SELECT count(*) FROM prepared_image_artifacts").fetchone() == (0,)
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert not {"audit_events_v0006", "stored_artifacts_v0007_new"} & names
    connection.close()


def test_pr011_win_003_windows_cipher_and_foreign_key_integrity_after_reopen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "pr011-win-integrity.db"
    key = b"i" * 32
    wrong_key = b"j" * 32
    _create_populated_encrypted_v6(path, key, monkeypatch)
    assert persistence_database.CURRENT_SCHEMA_VERSION == 7
    _migrate_encrypted_v7(path, key)
    raw = persistence_database._open_connection(path, Provider(key))
    assert not raw.in_transaction
    _cipher_active(raw)
    assert raw.execute("PRAGMA foreign_key_check").fetchall() == []
    assert raw.execute("PRAGMA cipher_integrity_check").fetchall() == []
    raw.close()
    reopened = EncryptedDatabase(path, Provider(key))
    reopened.initialize()
    with reopened.unit_of_work() as unit:
        connection = unit._connection()
        _cipher_active(connection)
        assert connection.execute("PRAGMA cipher_integrity_check").fetchall() == []
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA user_version").fetchone() == (7,)
        assert connection.execute("PRAGMA application_id").fetchone() == (APPLICATION_ID,)
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        assert {
            "prepared_image_artifacts_no_update",
            "prepared_image_artifacts_no_delete",
            "prepared_image_artifacts_no_replace",
            "prepared_image_artifacts_source_order_idx",
            "prepared_image_artifacts_recipe_order_idx",
        } <= names
        assert not {"audit_events_v0006", "stored_artifacts_v0007_new"} & names
    assert path.read_bytes()[:16] != b"SQLite format 3\x00"
    with (
        pytest.raises(PersistenceError) as rejected,
        EncryptedDatabase(path, Provider(wrong_key)).unit_of_work(),
    ):
        pass
    assert rejected.value.code is PersistenceErrorCode.DB_KEY_REJECTED
    captured = capsys.readouterr()
    rendered = captured.out + captured.err + caplog.text + str(rejected.value) + repr(reopened)
    for forbidden in (key.hex(), wrong_key.hex(), str(path), "000012345", "SELECT ", "sqlcipher3"):
        assert forbidden not in rendered


def test_pr011_win_004_windows_prepared_artifact_commit_reopen_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "pr011-win-prepared.db"
    key = b"p" * 32
    _create_populated_encrypted_v6(path, key, monkeypatch)
    assert persistence_database.CURRENT_SCHEMA_VERSION == 7
    database = _migrate_encrypted_v7(path, key)
    prepared = valid_prepared_artifact()
    stored = valid_prepared_stored_artifact()
    event = AuditEvent(
        entity_id(704),
        prepared.created_at,
        actor(),
        AuditAction.PREPARED_JPEG_CREATED,
        AuditSubjectType.PREPARED_IMAGE_ARTIFACT,
        prepared.id,
        reason_code=AuditReasonCode("PREPARED_JPEG_CREATED"),
        correlation_id=correlation_id(),
    )
    with database.unit_of_work() as unit:
        unit.stored_artifacts.add(stored)
        unit.prepared_image_artifacts.add(prepared)
        unit.audit_events.add(event)
        unit.commit()
    for _ in range(2):
        with EncryptedDatabase(path, Provider(key)).unit_of_work() as unit:
            assert unit.stored_artifacts.get(stored.artifact_id) == stored
            assert unit.prepared_image_artifacts.get(prepared.id) == prepared
            assert unit.audit_events.get(event.event_id) == event
            assert (
                unit.prepared_image_artifacts.get_by_natural_key(
                    prepared.geometry_recipe_version_id,
                    prepared.pipeline_id,
                    prepared.pipeline_version,
                    prepared.output_contract_id,
                    prepared.output_contract_version,
                )
                == prepared
            )
            assert unit.prepared_image_artifacts.list_by_source(prepared.source_file_id) == (
                prepared,
            )
            assert unit.prepared_image_artifacts.list_by_geometry_recipe(
                prepared.geometry_recipe_version_id
            ) == (prepared,)
            assert unit._connection().execute("PRAGMA foreign_keys").fetchone() == (1,)
            assert unit._connection().execute("PRAGMA foreign_key_check").fetchall() == []
            assert unit._connection().execute("PRAGMA cipher_integrity_check").fetchall() == []
    for statement in (
        "UPDATE prepared_image_artifacts SET width=width+1",
        "DELETE FROM prepared_image_artifacts",
        "INSERT OR REPLACE INTO prepared_image_artifacts SELECT * FROM prepared_image_artifacts",
    ):
        with EncryptedDatabase(path, Provider(key)).unit_of_work() as unit:
            with pytest.raises(Exception) as caught:
                unit._connection().execute(statement)
            assert (
                translate_driver_error(caught.value).code
                is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
            )
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(path).execute("SELECT count(*) FROM prepared_image_artifacts").fetchone()
