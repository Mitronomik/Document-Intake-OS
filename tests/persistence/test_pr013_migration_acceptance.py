from document_intake.persistence.migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS
from document_intake.persistence.migrations.v0008_document_regions import MIGRATION as V0008
from document_intake.persistence.migrations.v0009_document_side_composition import (
    MIGRATION as V0009,
)
from tests.persistence.test_migrations import apply


def test_fresh_schema_zero_to_nine_and_frozen_checksums() -> None:
    connection = apply()
    assert CURRENT_SCHEMA_VERSION == 9
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
    assert V0008.checksum == "ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b"
    assert V0009.name == "document_side_composition_pr013"
    assert V0009.checksum == "001795f9da8289fd9f06b1a4758e9153c34c2176867c30cb3c06a56bffaeb902"
    assert MIGRATIONS[-1] is V0009
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "document_side_compositions",
        "document_side_composition_versions",
        "prepared_composition_artifacts",
    } <= tables


def test_forward_audit_constraints_accept_only_new_typed_values() -> None:
    sql = V0009.statements[1]
    assert "DOCUMENT_SIDE_COMPOSITION_CREATED" in sql
    assert "DOCUMENT_SIDE_COMPOSITION" in sql
    assert "DOCUMENT_REGION_SET_CONFIRMED" in sql
