from __future__ import annotations

import ast
from pathlib import Path

import pytest

from document_intake.persistence import (
    APPLICATION_ID,
    CURRENT_SCHEMA_VERSION,
    PersistenceError,
    PersistenceErrorCode,
)
from document_intake.persistence.database import _apply_raw_hex_key, _validate_key
from document_intake.persistence.migrations.model import migration_checksum
from document_intake.persistence.migrations.v0001_initial import CHECKSUM, MIGRATION, STATEMENTS
from document_intake.persistence.migrations.v0002_stored_artifacts import (
    CHECKSUM as V0002_CHECKSUM,
)
from document_intake.persistence.migrations.v0002_stored_artifacts import (
    STATEMENTS as V0002_STATEMENTS,
)
from document_intake.persistence.migrations.v0003_audit_events import MIGRATION as V0003_MIGRATION
from document_intake.persistence.migrations.v0004_source_file_import import (
    MIGRATION as V0004_MIGRATION,
)
from document_intake.persistence.migrations.v0005_image_quality import MIGRATION as V0005_MIGRATION


class Provider:
    def __init__(self, value: object) -> None:
        self.value = value
        self.calls = 0

    def get_database_key(self) -> object:
        self.calls += 1
        return self.value


def test_package_imports_without_sqlcipher3_eager_import() -> None:
    import document_intake.persistence as persistence

    assert persistence.CURRENT_SCHEMA_VERSION == 5


def test_production_persistence_contains_no_sqlite3_import() -> None:
    for path in Path("src/document_intake/persistence").glob("**/*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name != "sqlite3" for alias in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert node.module != "sqlite3", path


def test_key_provider_requires_exact_bytes() -> None:
    valid = Provider(b"a" * 32)
    assert _validate_key(valid) == b"a" * 32
    assert valid.calls == 1
    for value in ("a" * 32, b"short", b"b" * 33):
        with pytest.raises(PersistenceError) as excinfo:
            _validate_key(Provider(value))  # type: ignore[arg-type]
        assert excinfo.value.code == PersistenceErrorCode.DB_KEY_INVALID
        assert "6161" not in str(excinfo.value)


def test_raw_key_helper_is_private_and_rejects_bad_key() -> None:
    with pytest.raises(PersistenceError) as excinfo:
        _apply_raw_hex_key(object(), b"short")  # type: ignore[arg-type]
    assert excinfo.value.code == PersistenceErrorCode.DB_KEY_INVALID


def test_migration_metadata_contract() -> None:
    assert CURRENT_SCHEMA_VERSION == 5
    assert APPLICATION_ID == 0x44494F53
    assert MIGRATION.version == 1
    assert MIGRATION.checksum == CHECKSUM
    assert migration_checksum(STATEMENTS) == CHECKSUM
    assert len(STATEMENTS) == 23
    assert V0002_CHECKSUM == "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d"
    assert migration_checksum(V0002_STATEMENTS) == V0002_CHECKSUM
    assert (
        V0003_MIGRATION.checksum
        == "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1"
    )
    assert (
        V0004_MIGRATION.checksum
        == "a826d5bc07ba73e6d54fd25e9df8afb42028261040b7981bdd157caf26b1f7c6"
    )
    assert (
        V0005_MIGRATION.checksum
        == "6d020d1acfbce3fcb7168e935617f2ae008a32bea7def1f37de84e36e9e2224f"
    )
    for table in (
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
    ):
        assert any(table in statement for statement in STATEMENTS)
