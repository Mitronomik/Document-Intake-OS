from __future__ import annotations

import importlib.metadata
import json
import platform
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from scripts import pr012_regions_verifier_support as pr012_support
from scripts import verify_pr012_regions as pr012_verifier

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
from document_intake.persistence.geometry_serialization import image_geometry_recipe_to_json
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


@contextmanager
def _historical_schema(version: int) -> Iterator[None]:
    previous_migrations = persistence_database.MIGRATIONS
    previous_version = persistence_database.CURRENT_SCHEMA_VERSION
    try:
        persistence_database.MIGRATIONS = MIGRATIONS[:version]
        persistence_database.CURRENT_SCHEMA_VERSION = version
        yield
    finally:
        persistence_database.MIGRATIONS = previous_migrations
        persistence_database.CURRENT_SCHEMA_VERSION = previous_version


def _insert_schema6_geometry(connection: Any) -> None:
    recipe = valid_geometry_recipe()
    payload = json.loads(image_geometry_recipe_to_json(recipe))
    del payload["region_id"]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    q = recipe.quadrilateral
    connection.execute(
        "INSERT INTO image_geometry_recipes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            str(recipe.recipe_version_id),
            str(recipe.source_file_id),
            None,
            recipe.revision,
            recipe.coordinate_space.value,
            recipe.source_effective_width,
            recipe.source_effective_height,
            int(recipe.quarter_turn),
            q.top_left.x,
            q.top_left.y,
            q.top_right.x,
            q.top_right.y,
            q.bottom_right.x,
            q.bottom_right.y,
            q.bottom_left.x,
            q.bottom_left.y,
            recipe.pipeline.pipeline_id,
            recipe.pipeline.version,
            recipe.created_at.isoformat().replace("+00:00", "Z"),
            canonical,
        ),
    )


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
    path: Path, key: bytes
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

    with _historical_schema(6):
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
            _insert_schema6_geometry(unit._connection())
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
    assert persistence_database.CURRENT_SCHEMA_VERSION == 8
    assert persistence_database._open_connection is production_open_connection
    reopened = persistence_database._open_connection(path, provider)
    expected = _rows(reopened)
    assert all(expected[table] for table in V6_TABLES)
    assert reopened.execute("PRAGMA foreign_key_check").fetchall() == []
    assert reopened.execute("PRAGMA cipher_integrity_check").fetchall() == []
    reopened.close()
    return expected


def _migrate_encrypted_v7(path: Path, key: bytes) -> EncryptedDatabase:
    with _historical_schema(7):
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
    with _historical_schema(7):
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
    tmp_path: Path,
) -> None:
    path = tmp_path / "pr011-win-v6.db"
    key = b"v" * 32
    expected = _create_populated_encrypted_v6(path, key)
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
    tmp_path: Path,
) -> None:
    path = tmp_path / "pr011-win-migration.db"
    key = b"m" * 32
    before = _create_populated_encrypted_v6(path, key)
    assert persistence_database.CURRENT_SCHEMA_VERSION == 8
    _migrate_encrypted_v7(path, key)
    connection = persistence_database._open_connection(path, Provider(key))
    assert connection.execute("PRAGMA user_version").fetchone() == (7,)
    history = connection.execute(
        "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    assert history == [(m.version, m.name, m.checksum) for m in MIGRATIONS[:7]]
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
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "pr011-win-integrity.db"
    key = b"i" * 32
    wrong_key = b"j" * 32
    _create_populated_encrypted_v6(path, key)
    assert persistence_database.CURRENT_SCHEMA_VERSION == 8
    _migrate_encrypted_v7(path, key)
    raw = persistence_database._open_connection(path, Provider(key))
    assert not raw.in_transaction
    _cipher_active(raw)
    assert raw.execute("PRAGMA foreign_key_check").fetchall() == []
    assert raw.execute("PRAGMA cipher_integrity_check").fetchall() == []
    raw.close()
    with _historical_schema(7):
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


def test_pr011_win_004_windows_prepared_artifact_commit_reopen_read(tmp_path: Path) -> None:
    path = tmp_path / "pr011-win-prepared.db"
    key = b"p" * 32
    _create_populated_encrypted_v6(path, key)
    assert persistence_database.CURRENT_SCHEMA_VERSION == 8
    _migrate_encrypted_v7(path, key)
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
    with _historical_schema(7):
        database = EncryptedDatabase(path, Provider(key))
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
            "INSERT OR REPLACE INTO prepared_image_artifacts "
            "SELECT * FROM prepared_image_artifacts",
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


def _pr012_scenario(tmp_path: Path) -> pr012_support.VerificationScenario:
    scenario = pr012_support.VerificationScenario(tmp_path)
    scenario.create_schema7()
    return scenario


def test_pr012_win_001_populated_encrypted_schema7_creation(tmp_path: Path) -> None:
    scenario = _pr012_scenario(tmp_path)
    fixture = scenario.fixture
    scenario.assert_schema7()
    assert scenario.encrypted_header()
    connection = scenario.open_connection()
    try:
        _cipher_active(connection)
        assert connection.execute("PRAGMA user_version").fetchone() == (7,)
        assert scenario.schema_history(connection) == tuple(
            (migration.version, migration.name, migration.checksum) for migration in MIGRATIONS[:7]
        )
        geometry = tuple(
            connection.execute(
                "SELECT recipe_version_id,source_file_id,superseded_recipe_version_id,revision "
                "FROM image_geometry_recipes ORDER BY source_file_id,revision"
            )
        )
        assert geometry == tuple(
            (
                str(recipe.recipe_version_id),
                str(recipe.source_file_id),
                None
                if recipe.superseded_recipe_version_id is None
                else str(recipe.superseded_recipe_version_id),
                recipe.revision,
            )
            for recipe in fixture.recipes
        )
        prepared = tuple(
            connection.execute(
                "SELECT prepared_artifact_id,geometry_recipe_version_id,stored_artifact_id "
                "FROM prepared_image_artifacts ORDER BY prepared_artifact_id"
            )
        )
        assert prepared == tuple(
            (
                str(item.id),
                str(item.geometry_recipe_version_id),
                str(item.stored_artifact_id),
            )
            for item in sorted(fixture.prepared, key=lambda value: str(value.id))
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA cipher_integrity_check").fetchall() == []
    finally:
        connection.close()
    assert scenario.plain_sqlite_rejected()


def test_pr012_win_002_production_populated_encrypted_v7_to_v8_migration(
    tmp_path: Path,
) -> None:
    scenario = _pr012_scenario(tmp_path)
    fixture = scenario.fixture
    scenario.migrate()
    scenario.assert_integrity()
    connection = scenario.open_connection()
    try:
        _cipher_active(connection)
        assert scenario.schema_history(connection) == tuple(
            (migration.version, migration.name, migration.checksum) for migration in MIGRATIONS
        )
        assert MIGRATIONS[7].checksum == pr012_support.MIGRATION.checksum
        rows = tuple(
            connection.execute(
                "SELECT recipe_version_id,region_id,superseded_recipe_version_id,revision "
                "FROM image_geometry_recipes ORDER BY source_file_id,revision"
            )
        )
        assert rows == tuple(
            (
                str(recipe.recipe_version_id),
                str(recipe.region_id),
                None
                if recipe.superseded_recipe_version_id is None
                else str(recipe.superseded_recipe_version_id),
                recipe.revision,
            )
            for recipe in fixture.recipes
        )
        prepared_refs = tuple(
            connection.execute(
                "SELECT prepared_artifact_id,geometry_recipe_version_id "
                "FROM prepared_image_artifacts ORDER BY prepared_artifact_id"
            )
        )
        assert prepared_refs == tuple(
            (str(item.id), str(item.geometry_recipe_version_id))
            for item in sorted(fixture.prepared, key=lambda value: str(value.id))
        )
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        assert "image_geometry_recipes_v0008_new" not in names
        assert "audit_events_v0007" not in names
        assert not {name for name in names if "v0008" in name}
    finally:
        connection.close()
    scenario.assert_migrated_repositories()


def test_pr012_win_003_encrypted_reopen_exact_repository_reads(tmp_path: Path) -> None:
    scenario = _pr012_scenario(tmp_path)
    fixture = scenario.fixture
    scenario.migrate()
    with scenario.database().unit_of_work() as unit:
        assert (
            tuple(
                unit.image_geometry_recipes.get(recipe.recipe_version_id)
                for recipe in fixture.recipes
            )
            == fixture.recipes
        )
        assert (
            unit.image_geometry_recipes.list_by_region(
                fixture.sources[0].id, fixture.source_a_recipes[0].region_id
            )
            == fixture.source_a_recipes
        )
        assert (
            unit.image_geometry_recipes.list_by_region(
                fixture.sources[1].id, fixture.source_b_recipes[0].region_id
            )
            == fixture.source_b_recipes
        )
        assert (
            unit.image_geometry_recipes.list_by_region(
                fixture.sources[0].id, fixture.source_b_recipes[0].region_id
            )
            == ()
        )
        assert (
            unit.image_geometry_recipes.list_by_region(
                fixture.sources[1].id, fixture.source_a_recipes[0].region_id
            )
            == ()
        )
        for expected in fixture.prepared:
            assert unit.prepared_image_artifacts.get(expected.id) == expected
            assert (
                unit.prepared_image_artifacts.get_by_natural_key(
                    expected.geometry_recipe_version_id,
                    expected.pipeline_id,
                    expected.pipeline_version,
                    expected.output_contract_id,
                    expected.output_contract_version,
                )
                == expected
            )
        connection = unit._connection()
        _cipher_active(connection)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA cipher_integrity_check").fetchall() == []


def test_pr012_win_004_first_production_region_confirmation(tmp_path: Path) -> None:
    scenario = _pr012_scenario(tmp_path)
    fixture = scenario.fixture
    scenario.migrate()
    created_set = scenario.run_confirmation(1)
    assert scenario.storage.publish_calls == 0
    assert (scenario.last_uow_calls, scenario.last_commits, scenario.last_rollbacks) == (2, 1, 0)
    with scenario.database().unit_of_work() as unit:
        a_history = unit.image_geometry_recipes.list_by_region(
            fixture.sources[0].id, fixture.source_a_recipes[0].region_id
        )
        c_history = unit.image_geometry_recipes.list_by_region(
            fixture.sources[0].id, created_set.members[1].region_id
        )
        assert a_history == fixture.source_a_recipes
        assert len(c_history) == 1
        assert c_history[0].recipe_version_id == created_set.members[1].geometry_recipe_version_id
        assert unit.document_region_sets.get(created_set.region_set_version_id) == created_set
        assert unit.document_region_sets.list_by_source(fixture.sources[0].id) == (created_set,)
        assert tuple(member.order_index for member in created_set.members) == (1, 2)
        recipe_audits = unit.audit_events.list_for_subject(
            AuditSubjectType.IMAGE_GEOMETRY_RECIPE, c_history[0].recipe_version_id
        )
        set_audits = unit.audit_events.list_for_subject(
            AuditSubjectType.DOCUMENT_REGION_SET, created_set.region_set_version_id
        )
        assert tuple(event.action_code for event in (*recipe_audits, *set_audits)) == (
            AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
            AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
        )
        assert len(recipe_audits) == len(set_audits) == 1


def test_pr012_win_005_second_confirmation_and_final_encrypted_reopen(
    tmp_path: Path,
) -> None:
    scenario = _pr012_scenario(tmp_path)
    fixture = scenario.fixture
    scenario.migrate()
    first = scenario.run_confirmation(1)
    assert (scenario.last_uow_calls, scenario.last_commits, scenario.last_rollbacks) == (2, 1, 0)
    second = scenario.run_confirmation(2)
    assert (scenario.last_uow_calls, scenario.last_commits, scenario.last_rollbacks) == (2, 1, 0)
    scenario.assert_product_state(2)
    scenario.assert_integrity()
    with scenario.database().unit_of_work() as unit:
        assert (
            unit.image_geometry_recipes.list_by_region(
                fixture.sources[0].id, fixture.source_a_recipes[0].region_id
            )
            == fixture.source_a_recipes
        )
        c_history = unit.image_geometry_recipes.list_by_region(
            fixture.sources[0].id, first.members[1].region_id
        )
        assert tuple(recipe.revision for recipe in c_history) == (1, 2)
        assert c_history[1].superseded_recipe_version_id == c_history[0].recipe_version_id
        assert unit.document_region_sets.list_by_source(fixture.sources[0].id) == (first, second)
        assert unit.document_region_sets.get_latest_by_source(fixture.sources[0].id) == second
        audit_rows = tuple(
            unit._connection().execute(
                "SELECT action_code,subject_id FROM audit_events "
                "WHERE action_code IN (?,?) ORDER BY occurred_at_utc,event_id",
                (
                    AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED.value,
                    AuditAction.DOCUMENT_REGION_SET_CONFIRMED.value,
                ),
            )
        )
        assert audit_rows == (
            (AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED.value, str(c_history[0].recipe_version_id)),
            (AuditAction.DOCUMENT_REGION_SET_CONFIRMED.value, str(first.region_set_version_id)),
            (AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED.value, str(c_history[1].recipe_version_id)),
            (AuditAction.DOCUMENT_REGION_SET_CONFIRMED.value, str(second.region_set_version_id)),
        )
        for expected in fixture.prepared:
            assert unit.prepared_image_artifacts.get(expected.id) == expected
        assert unit._connection().execute("PRAGMA foreign_key_check").fetchall() == []
        assert unit._connection().execute("PRAGMA cipher_integrity_check").fetchall() == []
    assert scenario.storage.publish_calls == 0


def test_pr012_win_006_populated_verifier_runtime_is_exact_and_private() -> None:
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/verify_pr012_regions.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0
    assert tuple(completed.stdout.splitlines()) == pr012_verifier._LABELS
    assert completed.stderr == ""
    assert not any(value in completed.stdout for value in pr012_verifier._PRIVACY_FORBIDDEN)
