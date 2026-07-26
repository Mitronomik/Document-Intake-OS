import inspect
import sqlite3

import pytest

from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_PIPELINE_ID,
)
from document_intake.persistence import database
from document_intake.persistence import serialization as ser
from document_intake.persistence.database import PreparedImageArtifactRepo
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.domain.test_prepared_jpeg import artifact


class _Uow:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def _connection(self) -> sqlite3.Connection:
        return self.connection

    def _invalidate_if_transaction_lost(self) -> None:
        return None


@pytest.fixture
def real_repo() -> tuple[sqlite3.Connection, PreparedImageArtifactRepo]:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    database._apply_migrations(connection)
    connection.execute("PRAGMA foreign_keys=OFF")
    return connection, PreparedImageArtifactRepo(_Uow(connection))  # type: ignore[arg-type]


def test_prepared_artifact_canonical_round_trip_has_no_bytes_or_paths() -> None:
    value = artifact()
    payload = ser.prepared_image_artifact_to_json(value)
    assert ser.prepared_image_artifact_from_json(payload) == value
    assert all(marker not in payload for marker in ("jpeg_bytes", "path", "filename"))


def test_repository_surface_is_create_once() -> None:
    assert hasattr(PreparedImageArtifactRepo, "add") and hasattr(PreparedImageArtifactRepo, "get")
    assert not hasattr(PreparedImageArtifactRepo, "update")
    assert not hasattr(PreparedImageArtifactRepo, "delete")
    assert not hasattr(PreparedImageArtifactRepo, "replace")


def test_real_repository_add_get_natural_key_and_lists(real_repo) -> None:  # type: ignore[no-untyped-def]
    _, repo = real_repo
    value = artifact()
    repo.add(value)
    assert repo.get(value.id) == value
    assert (
        repo.get_by_natural_key(
            value.geometry_recipe_version_id,
            PREPARED_JPEG_PIPELINE_ID,
            1,
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            1,
        )
        == value
    )
    assert repo.list_by_source(value.source_file_id) == (value,)
    assert repo.list_by_geometry_recipe(value.geometry_recipe_version_id) == (value,)


def test_real_repository_missing_queries_return_empty(real_repo) -> None:  # type: ignore[no-untyped-def]
    _, repo = real_repo
    value = artifact()
    assert repo.get(value.id) is None
    assert (
        repo.get_by_natural_key(
            value.geometry_recipe_version_id,
            PREPARED_JPEG_PIPELINE_ID,
            1,
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            1,
        )
        is None
    )
    assert repo.list_by_source(value.source_file_id) == ()


def test_real_repository_duplicate_id_is_controlled_and_preserves_first(real_repo) -> None:  # type: ignore[no-untyped-def]
    _, repo = real_repo
    value = artifact()
    repo.add(value)
    with pytest.raises(PersistenceError) as exc:
        repo.add(value)
    assert exc.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    assert repo.get(value.id) == value


@pytest.mark.parametrize(
    "payload",
    ["not-json", "{}", '{"unknown":true}'],
    ids=("malformed-json", "missing-keys", "unknown-key"),
)
def test_real_repository_rejects_canonical_corruption(real_repo, payload: str) -> None:  # type: ignore[no-untyped-def]
    connection, repo = real_repo
    value = artifact()
    repo.add(value)
    connection.execute("DROP TRIGGER prepared_image_artifacts_no_update")
    connection.execute(
        "UPDATE prepared_image_artifacts SET canonical_payload=? WHERE prepared_artifact_id=?",
        (payload, str(value.id)),
    )
    with pytest.raises(PersistenceError) as exc:
        repo.get(value.id)
    assert exc.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


@pytest.mark.parametrize("statement", ["UPDATE", "DELETE", "INSERT OR REPLACE", "REPLACE INTO"])
def test_database_immutability_rejects_every_mutation(real_repo, statement: str) -> None:  # type: ignore[no-untyped-def]
    connection, repo = real_repo
    value = artifact()
    repo.add(value)
    if statement == "UPDATE":
        sql = "UPDATE prepared_image_artifacts SET width=2 WHERE prepared_artifact_id=?"
    elif statement == "DELETE":
        sql = "DELETE FROM prepared_image_artifacts WHERE prepared_artifact_id=?"
    elif statement == "INSERT OR REPLACE":
        sql = (
            "INSERT OR REPLACE INTO prepared_image_artifacts SELECT * "
            "FROM prepared_image_artifacts WHERE prepared_artifact_id=?"
        )
    else:
        sql = (
            "REPLACE INTO prepared_image_artifacts SELECT * "
            "FROM prepared_image_artifacts WHERE prepared_artifact_id=?"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(sql, (str(value.id),))
    assert repo.get(value.id) == value


def test_public_queries_are_sql_scoped_and_deterministically_ordered() -> None:
    source = inspect.getsource(PreparedImageArtifactRepo)
    assert "def _all" not in source
    assert '"prepared_artifact_id=?"' in source
    assert '"source_file_id=?"' in source
    assert '"geometry_recipe_version_id=?"' in source
    assert "ORDER BY created_at_utc,prepared_artifact_id" in source
