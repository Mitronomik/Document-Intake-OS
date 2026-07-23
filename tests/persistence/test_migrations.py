from __future__ import annotations

import sqlite3

import pytest

from document_intake.persistence import database
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import APPLICATION_ID, CURRENT_SCHEMA_VERSION
from document_intake.persistence.migrations.model import Migration, migration_checksum
from document_intake.persistence.migrations.v0001_initial import MIGRATION
from document_intake.persistence.migrations.v0002_stored_artifacts import (
    MIGRATION as V0002_MIGRATION,
)
from document_intake.persistence.migrations.v0003_audit_events import MIGRATION as V0003_MIGRATION
from document_intake.persistence.migrations.v0004_source_file_import import (
    MIGRATION as V0004_MIGRATION,
)
from document_intake.persistence.migrations.v0005_image_quality import (
    MIGRATION as V0005_IMAGE_QUALITY,
)
from document_intake.persistence.migrations.v0006_image_geometry import (
    MIGRATION as V0006_IMAGE_GEOMETRY,
)

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
    "stored_artifacts",
    "audit_events",
    "upload_batches",
    "source_files",
    "upload_batch_source_files",
    "image_quality_assessments",
    "image_quality_metrics",
    "image_quality_issues",
    "image_geometry_recipes",
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
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall() == [
        (MIGRATION.version, MIGRATION.name, MIGRATION.checksum),
        (V0002_MIGRATION.version, V0002_MIGRATION.name, V0002_MIGRATION.checksum),
        (V0003_MIGRATION.version, V0003_MIGRATION.name, V0003_MIGRATION.checksum),
        (V0004_MIGRATION.version, V0004_MIGRATION.name, V0004_MIGRATION.checksum),
        (V0005_IMAGE_QUALITY.version, V0005_IMAGE_QUALITY.name, V0005_IMAGE_QUALITY.checksum),
        (V0006_IMAGE_GEOMETRY.version, V0006_IMAGE_GEOMETRY.name, V0006_IMAGE_GEOMETRY.checksum),
    ]


def test_initialize_migrations_are_idempotent() -> None:
    connection = apply()
    database._apply_migrations(connection)
    assert connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 6


def test_applied_prefix_validates_and_future_migration_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = apply()
    future_statements = ("CREATE TABLE future_projection(id INTEGER PRIMARY KEY)",)
    future = Migration(
        7,
        "future_projection",
        future_statements,
        migration_checksum(future_statements),
    )
    monkeypatch.setattr(
        database,
        "MIGRATIONS",
        (
            MIGRATION,
            V0002_MIGRATION,
            V0003_MIGRATION,
            V0004_MIGRATION,
            V0005_IMAGE_QUALITY,
            V0006_IMAGE_GEOMETRY,
            future,
        ),
    )
    monkeypatch.setattr(database, "CURRENT_SCHEMA_VERSION", 7)

    database._validate_schema(connection)
    database._apply_migrations(connection)

    assert connection.execute("PRAGMA user_version").fetchone()[0] == 7
    assert connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall() == [
        (MIGRATION.version, MIGRATION.name, MIGRATION.checksum),
        (V0002_MIGRATION.version, V0002_MIGRATION.name, V0002_MIGRATION.checksum),
        (V0003_MIGRATION.version, V0003_MIGRATION.name, V0003_MIGRATION.checksum),
        (V0004_MIGRATION.version, V0004_MIGRATION.name, V0004_MIGRATION.checksum),
        (V0005_IMAGE_QUALITY.version, V0005_IMAGE_QUALITY.name, V0005_IMAGE_QUALITY.checksum),
        (V0006_IMAGE_GEOMETRY.version, V0006_IMAGE_GEOMETRY.name, V0006_IMAGE_GEOMETRY.checksum),
        (future.version, future.name, future.checksum),
    ]
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name='future_projection'"
    ).fetchone() == ("future_projection",)


@pytest.mark.parametrize(
    "tamper",
    [
        lambda c: c.execute(
            "INSERT INTO schema_migrations(version, name, checksum, applied_at_utc) "
            "VALUES (7, 'extra', 'extra', '2026-07-19T00:00:00Z')"
        ),
        lambda c: c.execute("UPDATE schema_migrations SET name='reordered' WHERE version=1"),
        lambda c: (
            c.execute("ALTER TABLE schema_migrations RENAME TO malformed_history"),
            c.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)"),
        ),
    ],
)
def test_extra_reordered_or_malformed_history_is_rejected(tamper) -> None:  # type: ignore[no-untyped-def]
    connection = apply()
    tamper(connection)
    with pytest.raises(PersistenceError) as excinfo:
        database._validate_schema(connection)
    assert excinfo.value.code == PersistenceErrorCode.SCHEMA_HISTORY_INVALID


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
            PersistenceErrorCode.SCHEMA_HISTORY_INVALID,
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


def test_v0003_checksum_literal_and_prior_migrations_unchanged() -> None:
    assert MIGRATION.checksum == "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500"
    assert (
        V0002_MIGRATION.checksum
        == "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d"
    )
    assert V0003_MIGRATION.version == 3
    assert V0003_MIGRATION.name == "audit_events_pr007"
    assert (
        V0003_MIGRATION.checksum
        == "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1"
    )


def test_pr008_migration_metadata_and_checksums() -> None:
    assert V0004_MIGRATION.version == 4
    assert V0004_MIGRATION.name == "source_file_import_pr008"
    assert (
        V0004_MIGRATION.checksum
        == "a826d5bc07ba73e6d54fd25e9df8afb42028261040b7981bdd157caf26b1f7c6"
    )
    assert (
        V0002_MIGRATION.checksum
        == "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d"
    )
    assert (
        V0003_MIGRATION.checksum
        == "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1"
    )


def test_pr009_migration_metadata_and_checksums() -> None:
    assert V0005_IMAGE_QUALITY.version == 5
    assert V0005_IMAGE_QUALITY.name == "image_quality_pr009"
    assert (
        V0005_IMAGE_QUALITY.checksum
        == "6d020d1acfbce3fcb7168e935617f2ae008a32bea7def1f37de84e36e9e2224f"
    )


def test_v0005_preserves_historical_audit_rows_and_accepts_pr009_event_values() -> None:
    connection = apply_through_v0003()
    event_id = "00000000-0000-0000-0000-000000000701"
    actor_id = "00000000-0000-0000-0000-000000000702"
    subject_id = "00000000-0000-0000-0000-000000000703"
    connection.execute(
        "INSERT INTO audit_events(event_id, occurred_at_utc, actor_id, actor_kind, "
        "action_code, subject_type, subject_id, payload) "
        "VALUES (?, '2026-07-21T00:00:00Z', ?, 'SYSTEM', "
        "'ENTITY_CREATED', 'PERSON', ?, '{}')",
        (event_id, actor_id, subject_id),
    )

    database._apply_migrations(connection)

    assert connection.execute(
        "SELECT action_code, subject_type FROM audit_events WHERE event_id=?",
        (event_id,),
    ).fetchone() == ("ENTITY_CREATED", "PERSON")
    connection.execute(
        "INSERT INTO audit_events(event_id, occurred_at_utc, actor_id, actor_kind, "
        "action_code, subject_type, subject_id, payload) "
        "VALUES ('00000000-0000-0000-0000-000000000704', "
        "'2026-07-21T00:01:00Z', ?, 'SYSTEM', 'IMAGE_QUALITY_ASSESSED', "
        "'IMAGE_QUALITY_ASSESSMENT', ?, '{}')",
        (actor_id, subject_id),
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE audit_events SET subject_id=? WHERE event_id=?",
            (actor_id, event_id),
        )


def test_pr008_tables_exist_after_migration() -> None:
    connection = apply()
    assert table_columns(connection, "upload_batches")[:2] == ("id", "number")
    assert table_columns(connection, "source_files")[:3] == (
        "id",
        "batch_id",
        "original_artifact_id",
    )
    assert table_columns(connection, "upload_batch_source_files") == (
        "batch_id",
        "order_index",
        "source_file_id",
    )


def apply_through_v0003() -> sqlite3.Connection:
    connection = conn()
    connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    for migration in (MIGRATION, V0002_MIGRATION, V0003_MIGRATION):
        for statement in migration.statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations(version, name, checksum, applied_at_utc) "
            "VALUES (?, ?, ?, '2026-07-20T00:00:00Z')",
            (migration.version, migration.name, migration.checksum),
        )
        connection.execute(f"PRAGMA user_version = {migration.version}")
    return connection


def test_v0004_literal_metadata_and_all_prior_checksums_are_frozen() -> None:
    assert V0004_MIGRATION.version == 4
    assert V0004_MIGRATION.name == "source_file_import_pr008"
    assert (
        V0004_MIGRATION.checksum
        == "a826d5bc07ba73e6d54fd25e9df8afb42028261040b7981bdd157caf26b1f7c6"
    )
    assert MIGRATION.checksum == "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500"
    assert (
        V0002_MIGRATION.checksum
        == "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d"
    )
    assert (
        V0003_MIGRATION.checksum
        == "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1"
    )


def test_empty_database_and_upgrade_from_version_3_reach_exact_schema_6() -> None:
    empty = apply()
    assert empty.execute("PRAGMA user_version").fetchone()[0] == 6
    upgraded = apply_through_v0003()
    database._apply_migrations(upgraded)
    assert upgraded.execute("PRAGMA user_version").fetchone()[0] == 6
    assert upgraded.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone() == (6, V0006_IMAGE_GEOMETRY.name, V0006_IMAGE_GEOMETRY.checksum)


def test_v0004_column_constraints_foreign_keys_and_indexes() -> None:
    connection = apply()
    batch_info = {row[1]: row for row in connection.execute("PRAGMA table_info(upload_batches)")}
    source_info = {row[1]: row for row in connection.execute("PRAGMA table_info(source_files)")}
    membership_info = {
        row[1]: row for row in connection.execute("PRAGMA table_info(upload_batch_source_files)")
    }
    assert set(batch_info) == {
        "id",
        "number",
        "created_at_utc",
        "created_by_actor_id",
        "created_by_actor_kind",
        "status",
        "expected_source_file_count",
        "canonical_payload",
    }
    assert set(source_info) == {
        "id",
        "batch_id",
        "original_artifact_id",
        "original_basename",
        "detected_media_type",
        "byte_size",
        "sha256",
        "perceptual_algorithm_id",
        "perceptual_algorithm_version",
        "perceptual_bit_width",
        "perceptual_hex_value",
        "width",
        "height",
        "exif_orientation",
        "imported_at_utc",
        "imported_by_actor_id",
        "imported_by_actor_kind",
        "canonical_payload",
    }
    assert set(membership_info) == {"batch_id", "order_index", "source_file_id"}
    assert all(row[3] == 1 for name, row in batch_info.items() if name != "id")
    assert source_info["exif_orientation"][3] == 0
    assert all(
        row[3] == 1 for name, row in source_info.items() if name not in {"id", "exif_orientation"}
    )
    assert foreign_keys(connection, "source_files") >= {
        ("batch_id", "upload_batches", "id", "NO ACTION"),
        ("original_artifact_id", "stored_artifacts", "artifact_id", "NO ACTION"),
    }
    assert foreign_keys(connection, "upload_batch_source_files") >= {
        ("batch_id", "upload_batches", "id", "NO ACTION"),
        ("source_file_id", "source_files", "id", "NO ACTION"),
    }
    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name IN "
            "('upload_batches','source_files','upload_batch_source_files')"
        )
    }
    assert {
        "source_files_batch_order_idx",
        "source_files_sha_order_idx",
        "source_files_perceptual_order_idx",
        "upload_batch_source_files_order_idx",
    } <= indexes


def insert_batch(
    connection: sqlite3.Connection, *, value: int = 1, number: str = "BATCH-1"
) -> None:
    identifier = f"00000000-0000-0000-0000-{value:012d}"
    connection.execute(
        "INSERT INTO upload_batches VALUES (?, ?, '2026-07-20T00:00:00Z', "
        "'00000000-0000-0000-0000-000000000900', 'SYSTEM', 'NEW', 0, '{}')",
        (identifier, number),
    )


def insert_artifact(connection: sqlite3.Connection, value: int = 1001) -> None:
    identifier = f"00000000-0000-0000-0000-{value:012d}"
    connection.execute(
        "INSERT INTO stored_artifacts VALUES (?, 'ORIGINAL', 1, 1, ?, ?, 1, 1, "
        "'2026-07-20T00:00:00Z', '{}')",
        (identifier, "a" * 64, "b" * 64),
    )


def source_values() -> tuple[object, ...]:
    return (
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000001001",
        "synthetic.jpg",
        "JPEG",
        1,
        "c" * 64,
        "DHASH64",
        1,
        64,
        "0" * 16,
        9,
        8,
        None,
        "2026-07-20T00:00:00Z",
        "00000000-0000-0000-0000-000000000900",
        "SYSTEM",
        "{}",
    )


@pytest.mark.parametrize(
    ("index", "invalid"),
    [
        (4, "BMP"),
        (5, 0),
        (6, "A" * 64),
        (7, "OTHER"),
        (8, 2),
        (9, 63),
        (10, "G" * 16),
        (11, 0),
        (12, -1),
        (13, 0),
        (13, 9),
    ],
)
def test_v0004_source_enum_hash_dimension_and_orientation_constraints(
    index: int, invalid: object
) -> None:
    connection = apply()
    connection.execute("PRAGMA foreign_keys = ON")
    insert_batch(connection)
    insert_artifact(connection)
    values = list(source_values())
    values[index] = invalid
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO source_files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            values,
        )


def test_v0004_uniqueness_and_membership_order_constraints() -> None:
    connection = apply()
    connection.execute("PRAGMA foreign_keys = ON")
    insert_batch(connection)
    with pytest.raises(sqlite3.IntegrityError):
        insert_batch(connection, value=2, number="BATCH-1")
    insert_artifact(connection)
    connection.execute(
        "INSERT INTO source_files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", source_values()
    )
    connection.execute(
        "INSERT INTO upload_batch_source_files VALUES "
        "('00000000-0000-0000-0000-000000000001', 0, "
        "'00000000-0000-0000-0000-000000000001')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO upload_batch_source_files VALUES "
            "('00000000-0000-0000-0000-000000000001', -1, "
            "'00000000-0000-0000-0000-000000000001')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO source_files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", source_values()
        )


def test_v0004_failure_rolls_back_only_v0004(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = apply_through_v0003()
    bad = Migration(
        4,
        "source_file_import_pr008",
        (
            "CREATE TABLE before_v4_failure(id INTEGER)",
            "CREATE TABLE before_v4_failure(id INTEGER)",
        ),
        "synthetic-checksum",
    )
    monkeypatch.setattr(database, "MIGRATIONS", (MIGRATION, V0002_MIGRATION, V0003_MIGRATION, bad))
    with pytest.raises(PersistenceError) as caught:
        database._apply_migrations(connection)
    assert caught.value.code is PersistenceErrorCode.MIGRATION_FAILED
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    assert connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 3
    assert (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE name='before_v4_failure'"
        ).fetchone()
        is None
    )


def test_ordinary_sqlite_rejects_non_sqlite_encrypted_database_bytes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    encrypted = tmp_path / "encrypted-production-shape.db"
    encrypted.write_bytes(b"DIOS-SQLCIPHER-SYNTHETIC" + bytes(range(64)))
    connection = sqlite3.connect(encrypted)
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("SELECT name FROM sqlite_master").fetchall()
    connection.close()


def test_pr010_migration_metadata_checksum_and_columns() -> None:
    assert V0006_IMAGE_GEOMETRY.version == 6
    assert V0006_IMAGE_GEOMETRY.name == "image_geometry_pr010"
    assert (
        V0006_IMAGE_GEOMETRY.checksum
        == "ac9d5bfbe79160d880f30af6ee1ed645ab500b9be140a18b9d6498cc68eba5ec"
    )
    connection = apply()
    columns = [row[1] for row in connection.execute("PRAGMA table_info(image_geometry_recipes)")]
    assert columns == [
        "recipe_version_id",
        "source_file_id",
        "superseded_recipe_version_id",
        "revision",
        "coordinate_space",
        "source_effective_width",
        "source_effective_height",
        "quarter_turn_clockwise",
        "top_left_x",
        "top_left_y",
        "top_right_x",
        "top_right_y",
        "bottom_right_x",
        "bottom_right_y",
        "bottom_left_x",
        "bottom_left_y",
        "geometry_pipeline_id",
        "geometry_pipeline_version",
        "created_at_utc",
        "canonical_payload",
    ]
