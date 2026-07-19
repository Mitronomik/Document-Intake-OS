from __future__ import annotations

import sqlite3

import pytest

from document_intake.persistence import database
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import APPLICATION_ID, CURRENT_SCHEMA_VERSION
from document_intake.persistence.migrations.model import Migration, migration_checksum
from document_intake.persistence.migrations.v0001_initial import MIGRATION

REQUIRED_TABLES = {
    "schema_migrations",
    "persons",
    "identity_documents",
    "migration_documents",
    "documents",
    "document_sides",
    "vehicles",
    "terminals",
    "field_candidates",
    "field_candidate_validation_results",
    "applications",
    "application_assignments",
    "application_verified_fields",
    "application_validation_issues",
    "application_snapshots",
    "application_snapshot_artifact_refs",
}


def conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:", isolation_level=None)


def apply() -> sqlite3.Connection:
    connection = conn()
    database._apply_migrations(connection)
    return connection


def test_migration_1_creates_tables_metadata_user_version_and_application_id() -> None:
    connection = apply()
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert tables >= REQUIRED_TABLES
    assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert connection.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
    assert connection.execute(
        "SELECT version, name, checksum FROM schema_migrations"
    ).fetchone() == (
        MIGRATION.version,
        MIGRATION.name,
        MIGRATION.checksum,
    )


def test_initialize_migrations_are_idempotent() -> None:
    connection = apply()
    database._apply_migrations(connection)
    assert connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        (
            lambda c: c.execute("UPDATE schema_migrations SET checksum='bad'"),
            PersistenceErrorCode.SCHEMA_CHECKSUM_MISMATCH,
        ),
        (
            lambda c: c.execute("DELETE FROM schema_migrations"),
            PersistenceErrorCode.SCHEMA_HISTORY_INVALID,
        ),
        (
            lambda c: (
                c.execute("DELETE FROM schema_migrations"),
                c.execute(
                    "INSERT INTO schema_migrations(version, name, checksum, applied_at_utc) "
                    "VALUES (2, 'gap', 'x', '2026-07-19T00:00:00Z')"
                ),
                c.execute("PRAGMA user_version = 2"),
            ),
            PersistenceErrorCode.SCHEMA_VERSION_UNSUPPORTED,
        ),
        (
            lambda c: c.execute("PRAGMA user_version = 99"),
            PersistenceErrorCode.SCHEMA_VERSION_UNSUPPORTED,
        ),
    ],
)
def test_invalid_history_fails(setup, code: PersistenceErrorCode) -> None:  # type: ignore[no-untyped-def]
    connection = apply()
    setup(connection)
    with pytest.raises(PersistenceError) as excinfo:
        database._validate_schema(connection)
    assert excinfo.value.code == code


def test_non_empty_unmanaged_database_fails() -> None:
    connection = conn()
    connection.execute("CREATE TABLE unmanaged(id INTEGER PRIMARY KEY)")
    with pytest.raises(PersistenceError) as excinfo:
        database._apply_migrations(connection)
    assert excinfo.value.code == PersistenceErrorCode.SCHEMA_HISTORY_INVALID


def test_failed_migration_rolls_back_schema_history_user_version_and_application_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = Migration(
        1,
        "bad",
        (
            "CREATE TABLE before_failure(id INTEGER PRIMARY KEY)",
            "CREATE TABLE before_failure(id INTEGER PRIMARY KEY)",
        ),
        migration_checksum(
            (
                "CREATE TABLE before_failure(id INTEGER PRIMARY KEY)",
                "CREATE TABLE before_failure(id INTEGER PRIMARY KEY)",
            )
        ),
    )
    monkeypatch.setattr(database, "MIGRATIONS", (bad,))
    connection = conn()
    with pytest.raises(PersistenceError) as excinfo:
        database._apply_migrations(connection)
    assert excinfo.value.code == PersistenceErrorCode.MIGRATION_FAILED
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    assert connection.execute("PRAGMA application_id").fetchone()[0] == 0
    assert (
        connection.execute("SELECT name FROM sqlite_master WHERE name='before_failure'").fetchone()
        is None
    )
    assert (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE name='schema_migrations'"
        ).fetchone()
        is None
    )


def table_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table})"))


def foreign_keys(connection: sqlite3.Connection, table: str) -> set[tuple[str, str, str, str]]:
    return {
        (row[3], row[2], row[4], row[6])
        for row in connection.execute(f"PRAGMA foreign_key_list({table})")
    }


def test_application_and_snapshot_tables_store_canonical_payload_and_projections() -> None:
    connection = apply()
    assert table_columns(connection, "applications") == (
        "id",
        "batch_id",
        "terminal_code",
        "status",
        "created_by_actor_id",
        "created_by_actor_kind",
        "created_at_utc",
        "updated_at_utc",
        "payload",
    )
    snapshot_columns = table_columns(connection, "application_snapshots")
    assert "payload_json" in snapshot_columns
    assert "expected_artifact_ref_count" in snapshot_columns
    assert "payload" in snapshot_columns


def test_required_foreign_keys_are_restrict_and_no_false_foreign_keys_exist() -> None:
    connection = apply()
    assert ("person_id", "persons", "id", "RESTRICT") in foreign_keys(
        connection, "identity_documents"
    )
    assert ("person_id", "persons", "id", "RESTRICT") in foreign_keys(
        connection, "migration_documents"
    )
    assert ("related_passport_id", "identity_documents", "id", "RESTRICT") in foreign_keys(
        connection, "migration_documents"
    )
    assert ("terminal_code", "terminals", "code", "RESTRICT") in foreign_keys(
        connection, "applications"
    )
    assert ("application_id", "applications", "id", "RESTRICT") in foreign_keys(
        connection, "application_assignments"
    )
    assert ("person_id", "persons", "id", "RESTRICT") in foreign_keys(
        connection, "application_assignments"
    )
    assert ("tractor_id", "vehicles", "id", "RESTRICT") in foreign_keys(
        connection, "application_assignments"
    )
    assert ("trailer_id", "vehicles", "id", "RESTRICT") in foreign_keys(
        connection, "application_assignments"
    )
    assert ("source_candidate_id", "field_candidates", "id", "RESTRICT") in foreign_keys(
        connection, "application_verified_fields"
    )
    assert ("application_id", "applications", "id", "RESTRICT") in foreign_keys(
        connection, "application_verified_fields"
    )
    assert ("application_id", "applications", "id", "RESTRICT") in foreign_keys(
        connection, "application_validation_issues"
    )
    assert ("application_id", "applications", "id", "RESTRICT") in foreign_keys(
        connection, "application_snapshots"
    )
    assert ("terminal_code", "terminals", "code", "RESTRICT") in foreign_keys(
        connection, "application_snapshots"
    )
    assert ("snapshot_id", "application_snapshots", "id", "RESTRICT") in foreign_keys(
        connection, "application_snapshot_artifact_refs"
    )
    assert not foreign_keys(connection, "documents")
    assert not foreign_keys(connection, "vehicles")
    assert not foreign_keys(connection, "document_sides") - {
        ("document_id", "documents", "id", "RESTRICT")
    }
    assert all(fk[0] != "batch_id" for fk in foreign_keys(connection, "applications"))
