from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from document_intake.persistence import database
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS
from document_intake.persistence.migrations.model import Migration, migration_checksum
from document_intake.persistence.migrations.v0008_document_regions import MIGRATION as V0008
from document_intake.persistence.migrations.v0009_document_side_composition import (
    MIGRATION as V0009,
)
from tests.persistence.test_migrations import apply
from tests.support.pr013_persistence import (
    build_populated_schema8,
    snapshot_schema8_rows,
)

V0008_FROZEN_CHECKSUM = "ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b"
V0009_CANDIDATE_CHECKSUM = "0b0e0637ba4aa3defb29e6e27c241f28d333ec3c8bb6e8751c6cc7acc1b24b49"


def _history(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    return tuple(
        connection.execute(
            "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
    )


def _names(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}


def test_fresh_schema_zero_to_nine_and_frozen_checksums() -> None:
    connection = apply()
    assert CURRENT_SCHEMA_VERSION == 9
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
    assert V0008.checksum == V0008_FROZEN_CHECKSUM
    assert V0009.name == "document_side_composition_pr013"
    assert V0009.checksum == V0009_CANDIDATE_CHECKSUM
    assert MIGRATIONS[-1] is V0009
    assert _history(connection) == tuple(
        (migration.version, migration.name, migration.checksum) for migration in MIGRATIONS
    )
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert {
        "document_side_compositions",
        "document_side_composition_versions",
        "prepared_composition_artifacts",
        "document_side_composition_versions_side_1_lineage_guard",
        "document_side_composition_versions_side_2_lineage_guard",
    } <= _names(connection)


def test_forward_audit_constraints_accept_only_new_typed_values() -> None:
    sql = V0009.statements[1]
    assert "DOCUMENT_SIDE_COMPOSITION_CREATED" in sql
    assert "DOCUMENT_SIDE_COMPOSITION" in sql
    assert "DOCUMENT_REGION_SET_CONFIRMED" in sql


def test_populated_schema8_to_9_preserves_every_existing_row_after_reopen(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic-schema.sqlite"
    fixture = build_populated_schema8(path)
    expected_rows = fixture.rows
    expected_history = fixture.history
    assert expected_history == tuple(
        (migration.version, migration.name, migration.checksum) for migration in MIGRATIONS[:8]
    )
    database._apply_one_migration(fixture.connection, V0009)
    assert fixture.connection.execute("PRAGMA user_version").fetchone() == (9,)
    assert snapshot_schema8_rows(fixture.connection) == expected_rows
    assert _history(fixture.connection) == (
        *expected_history,
        (V0009.version, V0009.name, V0009.checksum),
    )
    assert fixture.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    fixture.connection.close()

    reopened = sqlite3.connect(path, isolation_level=None)
    reopened.execute("PRAGMA foreign_keys=ON")
    try:
        assert reopened.execute("PRAGMA user_version").fetchone() == (9,)
        assert snapshot_schema8_rows(reopened) == expected_rows
        assert _history(reopened)[-1] == (V0009.version, V0009.name, V0009.checksum)
        assert reopened.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        reopened.close()


def test_failed_v0009_rolls_back_schema_history_audit_rebuild_and_all_existing_rows() -> None:
    fixture = build_populated_schema8()
    connection = fixture.connection
    expected_rows = fixture.rows
    expected_history = fixture.history
    statements = (*V0009.statements[:13], "INVALID SYNTHETIC STATEMENT", *V0009.statements[13:])
    failing = Migration(
        9,
        V0009.name,
        statements,
        migration_checksum(statements, foreign_key_mode="DISABLED_DURING_TABLE_REBUILD"),
        foreign_key_mode="DISABLED_DURING_TABLE_REBUILD",
    )
    with pytest.raises(PersistenceError) as captured:
        database._apply_one_migration(connection, failing)
    assert captured.value.code is PersistenceErrorCode.MIGRATION_FAILED
    assert connection.execute("PRAGMA user_version").fetchone() == (8,)
    assert _history(connection) == expected_history
    assert snapshot_schema8_rows(connection) == expected_rows
    names = _names(connection)
    assert "audit_events" in names
    assert "audit_events_v0008" not in names
    assert "document_side_compositions" not in names
    assert "document_side_composition_versions" not in names
    assert "prepared_composition_artifacts" not in names
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
