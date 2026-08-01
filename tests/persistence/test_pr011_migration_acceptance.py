from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import AuditAction, AuditSubjectType, VehicleRole
from document_intake.domain.value_objects import AuditReasonCode
from document_intake.persistence import database, geometry_serialization
from document_intake.persistence.database import EncryptedDatabase, SqlCipherUnitOfWork
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import APPLICATION_ID, MIGRATIONS
from document_intake.persistence.migrations.v0007_prepared_jpeg import MIGRATION as V0007
from tests.persistence.test_repositories import (
    application,
    candidate,
    document,
    identity_document,
    migration_document,
    person,
    snapshot,
    terminal,
    vehicle,
)
from tests.support.pr011 import (
    Provider,
    actor,
    correlation_id,
    entity_id,
    open_sqlite,
    valid_audit_event,
    valid_geometry_recipe,
    valid_original_stored_artifact,
    valid_prepared_artifact,
    valid_prepared_stored_artifact,
    valid_quality_assessment,
    valid_source_file,
    valid_upload_batch,
)

V6_TABLES = (
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
)


@dataclass(frozen=True)
class Fixture:
    path: Path
    expected: dict[str, tuple[tuple[Any, ...], ...]]


def _snapshot(connection: sqlite3.Connection) -> dict[str, tuple[tuple[Any, ...], ...]]:
    return {
        table: tuple(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall())
        for table in (*V6_TABLES, "schema_migrations")
    }


def _configure(monkeypatch: pytest.MonkeyPatch, version: int) -> None:
    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    monkeypatch.setattr(database, "CURRENT_SCHEMA_VERSION", version)
    monkeypatch.setattr(database, "MIGRATIONS", MIGRATIONS[:version])


def _insert_schema6_geometry(connection: Any) -> None:
    recipe = valid_geometry_recipe()
    columns = geometry_serialization.image_geometry_recipe_columns(recipe)
    legacy_columns = (columns[0], columns[1], *columns[3:])
    payload = json.loads(geometry_serialization.image_geometry_recipe_to_json(recipe))
    payload.pop("region_id")
    connection.execute(
        "INSERT INTO image_geometry_recipes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*legacy_columns, json.dumps(payload, sort_keys=True, separators=(",", ":"))),
    )


def _build_v6(path: Path, monkeypatch: pytest.MonkeyPatch) -> Fixture:
    raw = open_sqlite(path)
    for migration in MIGRATIONS[:6]:
        database._apply_one_migration(raw, migration)
    assert raw.execute("PRAGMA user_version").fetchone() == (6,)
    assert raw.execute("PRAGMA application_id").fetchone() == (APPLICATION_ID,)
    assert raw.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert raw.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall() == [
        (number,) for number in range(1, 7)
    ]
    assert (
        raw.execute("SELECT 1 FROM sqlite_master WHERE name='prepared_image_artifacts'").fetchone()
        is None
    )
    raw.close()

    _configure(monkeypatch, 6)
    db = EncryptedDatabase(path, Provider())
    batch = valid_upload_batch()
    source = valid_source_file()
    original = valid_original_stored_artifact()
    refs = (
        replace(original, artifact_id=entity_id(81)),
        replace(original, artifact_id=entity_id(82)),
    )
    with db.unit_of_work() as unit:
        assert isinstance(unit, SqlCipherUnitOfWork)
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
        for record in refs:
            unit.stored_artifacts.add(record)
        unit.application_snapshots.add(snapshot(application()))
        unit.upload_batches.add(batch)
        unit.source_files.add(source)
        unit.upload_batches.update(batch.append_source_file_id(source.id))
        unit.image_quality_assessments.add(valid_quality_assessment())
        _insert_schema6_geometry(unit._connection())
        unit.audit_events.add(valid_audit_event())
        unit.commit()

    reopened = open_sqlite(path)
    expected = _snapshot(reopened)
    assert all(expected[table] for table in V6_TABLES)
    assert reopened.execute("PRAGMA foreign_key_check").fetchall() == []
    reopened.close()
    return Fixture(path, expected)


def _migrate(fixture: Fixture, monkeypatch: pytest.MonkeyPatch) -> EncryptedDatabase:
    _configure(monkeypatch, 7)
    db = EncryptedDatabase(fixture.path, Provider())
    db.initialize()
    return db


def test_pr011_mig_001_complete_populated_schema_v6_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_v6(tmp_path / "complete-v6.sqlite", monkeypatch)
    assert fixture.path.is_file()
    connection = open_sqlite(fixture.path)
    assert connection.execute("PRAGMA user_version").fetchone() == (6,)
    assert all(len(fixture.expected[table]) >= 1 for table in V6_TABLES)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    connection.close()
    with EncryptedDatabase(fixture.path, Provider()).unit_of_work() as unit:
        assert unit.persons.get(person().id) == person()
        assert unit.applications.get(application().id) == application()
        assert unit.source_files.get(valid_source_file().id) == valid_source_file()


def test_pr011_mig_002_all_populated_v6_rows_survive_v0007(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_v6(tmp_path / "survival.sqlite", monkeypatch)
    _migrate(fixture, monkeypatch)
    connection = open_sqlite(fixture.path)
    after = _snapshot(connection)
    assert {table: after[table] for table in V6_TABLES} == {
        table: fixture.expected[table] for table in V6_TABLES
    }
    assert connection.execute("SELECT count(*) FROM prepared_image_artifacts").fetchone() == (0,)
    connection.close()


def test_pr011_mig_003_migration_history_and_exact_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_v6(tmp_path / "history.sqlite", monkeypatch)
    _migrate(fixture, monkeypatch)
    connection = open_sqlite(fixture.path)
    history = connection.execute(
        "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    assert history == [(m.version, m.name, m.checksum) for m in MIGRATIONS[:7]]
    assert (V0007.version, V0007.name, V0007.checksum) == (
        7,
        "prepared_jpeg_pr011",
        "afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7",
    )
    assert connection.execute("PRAGMA user_version").fetchone() == (7,)
    assert connection.execute("PRAGMA application_id").fetchone() == (APPLICATION_ID,)
    connection.close()


def test_pr011_mig_004_foreign_key_and_integrity_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_v6(tmp_path / "integrity.sqlite", monkeypatch)
    _migrate(fixture, monkeypatch)
    for _ in range(2):
        connection = open_sqlite(fixture.path)
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master")}
        assert {
            "prepared_image_artifacts",
            "prepared_image_artifacts_source_order_idx",
            "prepared_image_artifacts_recipe_order_idx",
            "prepared_image_artifacts_no_update",
            "prepared_image_artifacts_no_delete",
            "prepared_image_artifacts_no_replace",
            "audit_events_no_update",
            "audit_events_no_delete",
            "stored_artifacts_no_update",
            "stored_artifacts_no_delete",
        } <= names
        assert not {"audit_events_v0006", "stored_artifacts_v0007_new"} & names
        assert not connection.in_transaction
        connection.close()


class _FailOnce:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.failed = False

    @property
    def in_transaction(self) -> bool:
        return self.connection.in_transaction

    def execute(self, statement: str, parameters: tuple[Any, ...] = ()) -> Any:
        cursor = self.connection.execute(statement, parameters)
        if not self.failed and "create table prepared_image_artifacts" in " ".join(
            statement.lower().split()
        ):
            self.failed = True
            raise sqlite3.OperationalError("synthetic interruption")
        return cursor

    def rollback(self) -> None:
        self.connection.rollback()

    def commit(self) -> None:
        self.connection.commit()


def test_pr011_mig_005_actual_v0007_rollback_and_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_v6(tmp_path / "retry.sqlite", monkeypatch)
    connection = open_sqlite(fixture.path)
    adapter = _FailOnce(connection)
    with pytest.raises(PersistenceError) as caught:
        database._apply_one_migration(adapter, V0007)  # type: ignore[arg-type]
    assert caught.value.code is PersistenceErrorCode.MIGRATION_FAILED
    assert str(fixture.path) not in str(caught.value)
    assert not connection.in_transaction
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert connection.execute("PRAGMA user_version").fetchone() == (6,)
    assert _snapshot(connection) == fixture.expected
    names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master")}
    assert (
        not {"audit_events_v0006", "stored_artifacts_v0007_new", "prepared_image_artifacts"} & names
    )
    connection.close()
    _migrate(fixture, monkeypatch)
    retry = open_sqlite(fixture.path)
    assert retry.execute("SELECT count(*) FROM schema_migrations WHERE version=7").fetchone() == (
        1,
    )
    assert retry.execute("PRAGMA user_version").fetchone() == (7,)
    retry.close()


def test_pr011_mig_006_production_sqlite_close_reopen_v6_to_v7(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_v6(tmp_path / "lifetimes.sqlite", monkeypatch)
    first = _migrate(fixture, monkeypatch)
    second = EncryptedDatabase(fixture.path, Provider())
    second.initialize()
    with second.unit_of_work() as unit:
        assert unit.persons.get(person().id) == person()
        assert unit._connection().execute("SELECT count(*) FROM schema_migrations").fetchone() == (
            7,
        )
        assert unit._connection().execute("PRAGMA foreign_key_check").fetchall() == []
    assert first is not second


def test_pr011_mig_007_prepared_artifact_commit_reopen_read_after_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _build_v6(tmp_path / "prepared.sqlite", monkeypatch)
    db = _migrate(fixture, monkeypatch)
    prepared = valid_prepared_artifact()
    stored = valid_prepared_stored_artifact()
    audit = AuditEvent(
        entity_id(700),
        prepared.created_at,
        actor(),
        AuditAction.PREPARED_JPEG_CREATED,
        AuditSubjectType.PREPARED_IMAGE_ARTIFACT,
        prepared.id,
        reason_code=AuditReasonCode("PREPARED_JPEG_CREATED"),
        correlation_id=correlation_id(),
    )
    with db.unit_of_work() as unit:
        unit.stored_artifacts.add(stored)
        unit.prepared_image_artifacts.add(prepared)
        unit.audit_events.add(audit)
        unit.commit()
    for _ in range(2):
        with EncryptedDatabase(fixture.path, Provider()).unit_of_work() as unit:
            assert unit.stored_artifacts.get(stored.artifact_id) == stored
            assert unit.prepared_image_artifacts.get(prepared.id) == prepared
            assert unit.audit_events.get(audit.event_id) == audit
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
            assert unit._connection().execute("PRAGMA foreign_key_check").fetchall() == []
            assert unit._connection().execute("PRAGMA integrity_check").fetchone() == ("ok",)
