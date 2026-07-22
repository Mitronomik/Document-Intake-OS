from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.persistence import database
from document_intake.persistence import serialization as ser
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations.v0001_initial import MIGRATION as V0001_MIGRATION
from document_intake.persistence.migrations.v0002_stored_artifacts import (
    MIGRATION as V0002_MIGRATION,
)
from document_intake.persistence.migrations.v0003_audit_events import (
    MIGRATION as V0003_MIGRATION,
)
from document_intake.persistence.migrations.v0004_source_file_import import (
    MIGRATION as V0004_MIGRATION,
)
from document_intake.persistence.migrations.v0005_image_quality import MIGRATION as V0005_MIGRATION


def memory_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    database._apply_migrations(connection)
    return connection


def _sqlite_uow_classes(monkeypatch: pytest.MonkeyPatch):
    from document_intake.persistence.database import SqlCipherUnitOfWork
    from tests.persistence.test_unit_of_work import Provider, open_sqlite

    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    return SqlCipherUnitOfWork, Provider


def _write_migrated_file(db, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.persistence.test_unit_of_work import migrated_file

    migrated_file(db)
    _sqlite_uow_classes(monkeypatch)


def _drop_stored_artifact_update_trigger(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TRIGGER stored_artifacts_no_update")


def record() -> StoredArtifactRecord:
    return StoredArtifactRecord(
        artifact_id=EntityId(uuid4()),
        artifact_kind=ArtifactKind.ORIGINAL,
        object_generation=1,
        plaintext_length=3,
        plaintext_sha256="a" * 64,
        ciphertext_sha256="b" * 64,
        key_version=1,
        storage_format_version=1,
        created_at=datetime.now(UTC),
    )


def test_v0001_checksum_unchanged_and_v0002_checksum_stable() -> None:
    assert (
        V0001_MIGRATION.checksum
        == "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500"
    )
    assert (
        V0002_MIGRATION.checksum
        == "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d"
    )


def test_clean_database_migrates_to_current_schema_and_preserves_v0002_history() -> None:
    connection = memory_connection()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    assert connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall() == [
        (1, V0001_MIGRATION.name, V0001_MIGRATION.checksum),
        (2, V0002_MIGRATION.name, V0002_MIGRATION.checksum),
        (3, V0003_MIGRATION.name, V0003_MIGRATION.checksum),
        (4, V0004_MIGRATION.name, V0004_MIGRATION.checksum),
        (5, V0005_MIGRATION.name, V0005_MIGRATION.checksum),
    ]


def test_v0002_digest_constraints_and_immutability_triggers() -> None:
    connection = memory_connection()
    good = record()
    payload = ser.stored_artifact_to_json(good)
    connection.execute(
        "INSERT INTO stored_artifacts(artifact_id, artifact_kind, object_generation, "
        "plaintext_length, "
        "plaintext_sha256, ciphertext_sha256, key_version, storage_format_version, "
        "created_at, "
        "canonical_payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (*ser.stored_artifact_columns(good), payload),
    )
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("UPDATE stored_artifacts SET plaintext_length=4")
    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("DELETE FROM stored_artifacts")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO stored_artifacts(artifact_id, artifact_kind, object_generation, "
            "plaintext_length, "
            "plaintext_sha256, ciphertext_sha256, key_version, storage_format_version, "
            "created_at, "
            "canonical_payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                str(EntityId(uuid4())),
                ArtifactKind.ORIGINAL.value,
                1,
                3,
                "g" * 64,
                "b" * 64,
                1,
                1,
                ser.utc_iso(datetime.now(UTC)),
                ser.stored_artifact_to_json(good),
            ),
        )


def test_stored_artifact_serialization_rejects_malformed_payloads() -> None:
    good = record()
    payload = ser.stored_artifact_to_json(good)
    assert ser.stored_artifact_from_json(payload) == good
    for malformed in (
        payload.replace('"key_version":1', '"key_version":true'),
        payload[:-1] + ',"extra":1}',
        payload.replace('"created_at":"', '"created_at":"not-a-date'),
    ):
        with pytest.raises(PersistenceError) as error:
            ser.stored_artifact_from_json(malformed)
        assert error.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_stored_artifact_uow_commit_rollback_and_uncommitted_exit(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from document_intake.persistence.database import SqlCipherUnitOfWork
    from tests.persistence.test_unit_of_work import Provider, migrated_file, open_sqlite

    db = tmp_path / "stored.db"
    migrated_file(db)
    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    first = record()
    with pytest.raises(PersistenceError):
        SqlCipherUnitOfWork(db, Provider()).stored_artifacts.list_all()
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        assert not hasattr(uow.stored_artifacts, "update")
        assert not hasattr(uow.stored_artifacts, "delete")
        uow.stored_artifacts.add(first)
        assert uow.stored_artifacts.get(first.artifact_id) == first
        assert uow.stored_artifacts.list_all() == (first,)
        uow.commit()
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        assert uow.stored_artifacts.get(first.artifact_id) == first
        with pytest.raises(PersistenceError):
            uow.stored_artifacts.add(first)
        uow.rollback()
    rolled_back = record()
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        uow.stored_artifacts.add(rolled_back)
        uow.rollback()
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        assert uow.stored_artifacts.get(rolled_back.artifact_id) is None
    uncommitted = record()
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        uow.stored_artifacts.add(uncommitted)
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        assert uow.stored_artifacts.get(uncommitted.artifact_id) is None


def test_stored_artifact_repository_projection_mismatches_are_invalid(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from document_intake.persistence.database import SqlCipherUnitOfWork
    from tests.persistence.test_unit_of_work import Provider, migrated_file, open_sqlite

    columns_and_values = {
        "artifact_id": str(EntityId(uuid4())),
        "artifact_kind": ArtifactKind.PREPARED_DOCUMENT.value,
        "object_generation": 2,
        "plaintext_length": 4,
        "plaintext_sha256": "c" * 64,
        "ciphertext_sha256": "d" * 64,
        "key_version": 2,
        "storage_format_version": 2,
        "created_at": ser.utc_iso(datetime(2026, 1, 1, tzinfo=UTC)),
    }
    for column, value in columns_and_values.items():
        db = tmp_path / f"tamper-{column}.db"
        migrated_file(db)
        monkeypatch.setattr(database, "_open_connection", open_sqlite)
        base = record()
        with SqlCipherUnitOfWork(db, Provider()) as uow:
            uow.stored_artifacts.add(base)
            uow.commit()
        raw = sqlite3.connect(db, isolation_level=None)
        _drop_stored_artifact_update_trigger(raw)
        raw.execute("PRAGMA ignore_check_constraints = ON")
        raw.execute(
            f"UPDATE stored_artifacts SET {column}=? WHERE artifact_id=?",
            (value, str(base.artifact_id)),
        )
        raw.close()
        with SqlCipherUnitOfWork(db, Provider()) as uow:
            with pytest.raises(PersistenceError) as error:
                if column == "artifact_id":
                    uow.stored_artifacts.list_all()
                else:
                    uow.stored_artifacts.get(base.artifact_id)
            assert error.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
            rendered = f"{error.value!s} {error.value!r}"
            assert "SELECT" not in rendered
            assert "stored_artifacts" not in rendered
            assert base.plaintext_sha256 not in rendered

    payload_mutations = {
        "missing_field": lambda d: d.pop("artifact_kind"),
        "extra_field": lambda d: d.update({"extra": 1}),
        "invalid_uuid": lambda d: d.update({"artifact_id": "not-a-uuid"}),
        "invalid_kind": lambda d: d.update({"artifact_kind": "OTHER"}),
        "bool_integer": lambda d: d.update({"key_version": True}),
        "zero_key": lambda d: d.update({"key_version": 0}),
        "negative_key": lambda d: d.update({"key_version": -1}),
        "unsupported_generation": lambda d: d.update({"object_generation": 2}),
        "unsupported_format": lambda d: d.update({"storage_format_version": 2}),
        "malformed_digest": lambda d: d.update({"plaintext_sha256": "g" * 64}),
        "malformed_datetime": lambda d: d.update({"created_at": "not-a-date"}),
        "naive_datetime": lambda d: d.update({"created_at": "2026-07-19T00:00:00"}),
        "artifact_id_mismatch": lambda d: d.update({"artifact_id": str(EntityId(uuid4()))}),
    }
    for name, mutate in payload_mutations.items():
        db = tmp_path / f"payload-{name}.db"
        migrated_file(db)
        base = record()
        with SqlCipherUnitOfWork(db, Provider()) as uow:
            uow.stored_artifacts.add(base)
            uow.commit()
        raw = sqlite3.connect(db, isolation_level=None)
        payload = raw.execute(
            "SELECT canonical_payload FROM stored_artifacts WHERE artifact_id=?",
            (str(base.artifact_id),),
        ).fetchone()[0]
        parsed = json.loads(payload)
        mutate(parsed)
        corrupted = ser.dumps(parsed)
        _drop_stored_artifact_update_trigger(raw)
        raw.execute(
            "UPDATE stored_artifacts SET canonical_payload=? WHERE artifact_id=?",
            (corrupted, str(base.artifact_id)),
        )
        raw.close()
        with SqlCipherUnitOfWork(db, Provider()) as uow:
            with pytest.raises(PersistenceError) as error:
                uow.stored_artifacts.get(base.artifact_id)
            assert error.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID

    db = tmp_path / "payload-malformed-json.db"
    migrated_file(db)
    base = record()
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        uow.stored_artifacts.add(base)
        uow.commit()
    raw = sqlite3.connect(db, isolation_level=None)
    _drop_stored_artifact_update_trigger(raw)
    raw.execute(
        "UPDATE stored_artifacts SET canonical_payload=? WHERE artifact_id=?",
        ("{not-json", str(base.artifact_id)),
    )
    raw.close()
    with SqlCipherUnitOfWork(db, Provider()) as uow:
        with pytest.raises(PersistenceError) as error:
            uow.stored_artifacts.get(base.artifact_id)
        assert error.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_v0001_to_v0002_preserves_populated_rows() -> None:
    from document_intake.persistence.migrations import MIGRATIONS
    from document_intake.persistence.migrations.v0001_initial import MIGRATION as V1

    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("PRAGMA application_id = 0x44494F53")
    for statement in V1.statements:
        connection.execute(statement)
    connection.execute(
        "INSERT INTO schema_migrations(version, name, checksum, applied_at_utc) VALUES (?,?,?,?)",
        (V1.version, V1.name, V1.checksum, "2026-07-19T00:00:00Z"),
    )
    connection.execute("PRAGMA user_version = 1")
    connection.execute("PRAGMA foreign_keys = ON")
    payload = '{"synthetic":"pr006"}'
    connection.execute(
        "INSERT INTO persons(id, payload) VALUES (?,?)",
        ("00000000-0000-0000-0000-000000000001", payload),
    )
    connection.execute(
        "INSERT INTO identity_documents(id, person_id, payload) VALUES (?,?,?)",
        (
            "00000000-0000-0000-0000-000000000011",
            "00000000-0000-0000-0000-000000000001",
            payload,
        ),
    )
    connection.execute(
        "INSERT INTO documents(id, owner_kind, owner_id, payload) VALUES (?,?,?,?)",
        (
            "00000000-0000-0000-0000-000000000021",
            "PERSON",
            "00000000-0000-0000-0000-000000000001",
            payload,
        ),
    )
    connection.execute(
        "INSERT INTO document_sides(document_id, order_index, side_id) VALUES (?,?,?)",
        ("00000000-0000-0000-0000-000000000021", 0, "front"),
    )
    connection.execute(
        "INSERT INTO vehicles(id, payload) VALUES (?,?)",
        ("00000000-0000-0000-0000-000000000002", payload),
    )
    connection.execute(
        "INSERT INTO vehicles(id, payload) VALUES (?,?)",
        ("00000000-0000-0000-0000-000000000003", payload),
    )
    connection.execute(
        "INSERT INTO terminals(code, is_active, payload) VALUES (?,?,?)",
        ("SYN", 1, payload),
    )
    connection.execute(
        "INSERT INTO applications(id, batch_id, terminal_code, status, created_by_actor_id, "
        "created_by_actor_kind, created_at_utc, updated_at_utc, payload) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "00000000-0000-0000-0000-000000000031",
            "batch-synthetic",
            "SYN",
            "DRAFT",
            "00000000-0000-0000-0000-000000000041",
            "SYSTEM",
            "2026-07-19T00:00:00Z",
            "2026-07-19T00:00:00Z",
            payload,
        ),
    )
    connection.execute(
        "INSERT INTO application_assignments(application_id, order_index, person_id, "
        "tractor_id, trailer_id, payload) VALUES (?,?,?,?,?,?)",
        (
            "00000000-0000-0000-0000-000000000031",
            0,
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            "00000000-0000-0000-0000-000000000003",
            payload,
        ),
    )
    connection.execute(
        "INSERT INTO application_snapshots(id, application_id, terminal_code, template_version, "
        "rules_version, created_by_actor_id, created_by_actor_kind, created_at_utc, "
        "payload_json, sha256, expected_artifact_ref_count, payload) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "00000000-0000-0000-0000-000000000051",
            "00000000-0000-0000-0000-000000000031",
            "SYN",
            "template-v1",
            "rules-v1",
            "00000000-0000-0000-0000-000000000041",
            "SYSTEM",
            "2026-07-19T00:00:00Z",
            payload,
            "a" * 64,
            1,
            payload,
        ),
    )
    connection.execute(
        "INSERT INTO application_snapshot_artifact_refs(snapshot_id, order_index, artifact_ref) "
        "VALUES (?,?,?)",
        ("00000000-0000-0000-0000-000000000051", 0, "opaque-artifact-ref"),
    )
    populated_tables = (
        "persons",
        "identity_documents",
        "documents",
        "document_sides",
        "vehicles",
        "terminals",
        "applications",
        "application_assignments",
        "application_snapshots",
        "application_snapshot_artifact_refs",
    )
    before = {
        table: tuple(connection.execute(f"SELECT * FROM {table}").fetchall())
        for table in populated_tables
    }
    before_history = tuple(
        connection.execute("SELECT version, name, checksum FROM schema_migrations").fetchall()
    )
    assert before_history == ((1, V1.name, V1.checksum),)
    assert (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stored_artifacts'"
        ).fetchone()
        is None
    )
    connection.execute("COMMIT")
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert len(MIGRATIONS) >= 2
    assert MIGRATIONS[1].version == 2
    assert MIGRATIONS[1].checksum == V0002_MIGRATION.checksum
    database._apply_migrations(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    assert connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall() == [
        (1, V1.name, V1.checksum),
        (2, V0002_MIGRATION.name, V0002_MIGRATION.checksum),
        (3, V0003_MIGRATION.name, V0003_MIGRATION.checksum),
        (4, V0004_MIGRATION.name, V0004_MIGRATION.checksum),
        (5, V0005_MIGRATION.name, V0005_MIGRATION.checksum),
    ]
    for table, rows in before.items():
        assert tuple(connection.execute(f"SELECT * FROM {table}").fetchall()) == rows
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("SELECT count(*) FROM stored_artifacts").fetchone()[0] == 0
    assert (
        connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='trigger' "
            "AND name IN ('stored_artifacts_no_update','stored_artifacts_no_delete')"
        ).fetchone()[0]
        == 2
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO stored_artifacts(artifact_id, artifact_kind, object_generation, "
            "plaintext_length, plaintext_sha256, ciphertext_sha256, key_version, "
            "storage_format_version, created_at, canonical_payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                str(EntityId(uuid4())),
                ArtifactKind.ORIGINAL.value,
                1,
                1,
                "g" * 64,
                "b" * 64,
                1,
                1,
                ser.utc_iso(datetime.now(UTC)),
                ser.stored_artifact_to_json(record()),
            ),
        )
