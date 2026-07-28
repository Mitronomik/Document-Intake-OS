from __future__ import annotations

import inspect
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

import pytest

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import AuditAction, AuditSubjectType
from document_intake.domain.prepared_jpeg import (
    PreparedImageArtifact,
)
from document_intake.domain.value_objects import AuditReasonCode, EntityId
from document_intake.persistence import database
from document_intake.persistence.database import EncryptedDatabase, SqlCipherUnitOfWork
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import (
    STAMP,
    Provider,
    actor,
    correlation_id,
    entity_id,
    valid_geometry_recipe,
    valid_original_stored_artifact,
    valid_prepared_artifact,
    valid_prepared_stored_artifact,
    valid_source_file,
    valid_upload_batch,
)


def sqlite_connection(path: Path, provider: object) -> sqlite3.Connection:
    del provider
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@dataclass(frozen=True, slots=True)
class RepositoryEnvironment:
    database: EncryptedDatabase
    path: Path
    recipes: tuple[object, object, object]
    production_sqlcipher: bool


@pytest.fixture
def repository_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> RepositoryEnvironment:
    production_sqlcipher = sys.platform == "win32"
    if not production_sqlcipher:
        monkeypatch.setattr(database, "_open_connection", sqlite_connection)
    path = tmp_path / "repository-core.db"
    encrypted = EncryptedDatabase(path, Provider())
    encrypted.initialize()
    first = valid_geometry_recipe()
    second = replace(
        first,
        recipe_version_id=entity_id(31),
        superseded_recipe_version_id=first.recipe_version_id,
        revision=2,
        created_at=STAMP + timedelta(seconds=1),
    )
    third = replace(
        first,
        recipe_version_id=entity_id(32),
        superseded_recipe_version_id=second.recipe_version_id,
        revision=3,
        created_at=STAMP + timedelta(seconds=2),
    )
    batch = valid_upload_batch()
    source = valid_source_file()
    with encrypted.unit_of_work() as unit:
        assert_foreign_keys(unit)
        unit.upload_batches.add(batch)
        unit.stored_artifacts.add(valid_original_stored_artifact())
        unit.source_files.add(source)
        unit.upload_batches.update(batch.append_source_file_id(source.id))
        for recipe in (first, second, third):
            unit.image_geometry_recipes.add(recipe)
        unit.commit()
    return RepositoryEnvironment(encrypted, path, (first, second, third), production_sqlcipher)


def assert_foreign_keys(unit: SqlCipherUnitOfWork) -> None:
    connection = unit._connection()
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)


def assert_integrity(unit: SqlCipherUnitOfWork) -> None:
    assert_foreign_keys(unit)
    assert unit._connection().execute("PRAGMA foreign_key_check").fetchall() == []


@contextmanager
def production_uow(environment: RepositoryEnvironment) -> Iterator[SqlCipherUnitOfWork]:
    with environment.database.unit_of_work() as unit:
        assert isinstance(unit, SqlCipherUnitOfWork)
        assert_foreign_keys(unit)
        yield unit


def prepared(
    number: int,
    recipe_id: EntityId,
    stored_id: EntityId,
    *,
    created_offset: int = 0,
    prepared_id: EntityId | None = None,
) -> PreparedImageArtifact:
    return replace(
        valid_prepared_artifact(),
        id=prepared_id or entity_id(number),
        geometry_recipe_version_id=recipe_id,
        stored_artifact_id=stored_id,
        created_at=STAMP + timedelta(seconds=created_offset),
    )


def stored(number: int, artifact: PreparedImageArtifact) -> StoredArtifactRecord:
    return replace(
        valid_prepared_stored_artifact(),
        artifact_id=entity_id(number),
        plaintext_length=artifact.byte_size,
        plaintext_sha256=artifact.sha256.value,
        created_at=artifact.created_at,
    )


def audit(number: int, artifact: PreparedImageArtifact) -> AuditEvent:
    return AuditEvent(
        entity_id(number),
        artifact.created_at,
        actor(),
        AuditAction.PREPARED_JPEG_CREATED,
        AuditSubjectType.PREPARED_IMAGE_ARTIFACT,
        artifact.id,
        reason_code=AuditReasonCode("PREPARED_JPEG_CREATED"),
        correlation_id=correlation_id(),
    )


def add_complete(
    unit: SqlCipherUnitOfWork,
    artifact: PreparedImageArtifact,
    *,
    stored_number: int,
    audit_number: int,
) -> tuple[StoredArtifactRecord, AuditEvent]:
    record = stored(stored_number, artifact)
    event = audit(audit_number, artifact)
    unit.stored_artifacts.add(record)
    unit.prepared_image_artifacts.add(artifact)
    unit.audit_events.add(event)
    return record, event


def test_pr011_rep_001_production_encrypted_database_unit_of_work_fixture(
    repository_environment: RepositoryEnvironment,
) -> None:
    candidate = repository_environment.database.unit_of_work()
    assert type(candidate) is SqlCipherUnitOfWork
    with candidate as unit:
        connection = unit._connection()
        if repository_environment.production_sqlcipher:
            cipher_version = connection.execute("PRAGMA cipher_version").fetchone()
            assert cipher_version is not None
            assert isinstance(cipher_version[0], str)
            assert cipher_version[0].strip()
        else:
            assert sys.platform != "win32"
            assert database._open_connection is sqlite_connection
            assert connection.execute("PRAGMA cipher_version").fetchone() is None
        assert unit.prepared_image_artifacts.get(entity_id(400)) is None
        assert_integrity(unit)


def test_pr011_rep_002_foreign_keys_enabled_for_every_repository_uow(
    repository_environment: RepositoryEnvironment,
) -> None:
    with production_uow(repository_environment) as unit:
        artifact = prepared(
            400, repository_environment.recipes[0].recipe_version_id, entity_id(401)
        )
        add_complete(unit, artifact, stored_number=401, audit_number=402)
        unit.commit()
    with production_uow(repository_environment) as reopened:
        assert_integrity(reopened)
        assert reopened.prepared_image_artifacts.get(artifact.id) == artifact


def test_pr011_rep_003_add_without_commit_rolls_back(
    repository_environment: RepositoryEnvironment,
) -> None:
    artifact = prepared(410, repository_environment.recipes[0].recipe_version_id, entity_id(411))
    with production_uow(repository_environment) as unit:
        add_complete(unit, artifact, stored_number=411, audit_number=412)
    with production_uow(repository_environment) as reopened:
        assert reopened.prepared_image_artifacts.get(artifact.id) is None
        assert reopened.stored_artifacts.get(entity_id(411)) is None
        assert reopened.audit_events.get(entity_id(412)) is None
        assert_integrity(reopened)


def test_pr011_rep_004_add_with_commit_survives_independent_reopen(
    repository_environment: RepositoryEnvironment,
) -> None:
    artifact = prepared(420, repository_environment.recipes[0].recipe_version_id, entity_id(421))
    with production_uow(repository_environment) as unit:
        record, event = add_complete(unit, artifact, stored_number=421, audit_number=422)
        unit.commit()
    with production_uow(repository_environment) as reopened:
        assert reopened.stored_artifacts.get(record.artifact_id) == record
        assert reopened.prepared_image_artifacts.get(artifact.id) == artifact
        assert reopened.audit_events.get(event.event_id) == event
        assert_integrity(reopened)


def test_pr011_rep_005_exception_before_commit_rolls_back(
    repository_environment: RepositoryEnvironment,
) -> None:
    artifact = prepared(430, repository_environment.recipes[0].recipe_version_id, entity_id(431))
    with (
        pytest.raises(RuntimeError, match="SYNTHETIC_PRECOMMIT_FAILURE"),
        production_uow(repository_environment) as unit,
    ):
        add_complete(unit, artifact, stored_number=431, audit_number=432)
        raise RuntimeError("SYNTHETIC_PRECOMMIT_FAILURE")
    with production_uow(repository_environment) as reopened:
        assert reopened.prepared_image_artifacts.get(artifact.id) is None
        assert reopened.stored_artifacts.get(entity_id(431)) is None
        assert reopened.audit_events.get(entity_id(432)) is None
        assert_integrity(reopened)


def commit_first(environment: RepositoryEnvironment) -> PreparedImageArtifact:
    first = prepared(440, environment.recipes[0].recipe_version_id, entity_id(441))
    with production_uow(environment) as unit:
        add_complete(unit, first, stored_number=441, audit_number=442)
        unit.commit()
    return first


def test_pr011_rep_006_duplicate_prepared_artifact_id_preserves_first(
    repository_environment: RepositoryEnvironment,
) -> None:
    first = commit_first(repository_environment)
    duplicate = prepared(
        443,
        repository_environment.recipes[1].recipe_version_id,
        entity_id(444),
        prepared_id=first.id,
    )
    with (
        pytest.raises(PersistenceError) as caught,
        production_uow(repository_environment) as unit,
    ):
        unit.stored_artifacts.add(stored(444, duplicate))
        unit.prepared_image_artifacts.add(duplicate)
        unit.commit()
    assert caught.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    with production_uow(repository_environment) as reopened:
        assert reopened.prepared_image_artifacts.get(first.id) == first
        assert reopened.stored_artifacts.get(entity_id(444)) is None
        assert_integrity(reopened)


def test_pr011_rep_007_duplicate_stored_artifact_reference_preserves_first(
    repository_environment: RepositoryEnvironment,
) -> None:
    first = commit_first(repository_environment)
    duplicate = prepared(
        450, repository_environment.recipes[1].recipe_version_id, first.stored_artifact_id
    )
    with (
        pytest.raises(PersistenceError) as caught,
        production_uow(repository_environment) as unit,
    ):
        unit.prepared_image_artifacts.add(duplicate)
        unit.commit()
    assert caught.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    with production_uow(repository_environment) as reopened:
        assert reopened.prepared_image_artifacts.get(first.id) == first
        assert reopened.prepared_image_artifacts.get(duplicate.id) is None
        assert_integrity(reopened)


def test_pr011_rep_008_duplicate_natural_key_preserves_first(
    repository_environment: RepositoryEnvironment,
) -> None:
    first = commit_first(repository_environment)
    duplicate = prepared(460, first.geometry_recipe_version_id, entity_id(461))
    with (
        pytest.raises(PersistenceError) as caught,
        production_uow(repository_environment) as unit,
    ):
        unit.stored_artifacts.add(stored(461, duplicate))
        unit.prepared_image_artifacts.add(duplicate)
        unit.commit()
    assert caught.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    with production_uow(repository_environment) as reopened:
        assert reopened.prepared_image_artifacts.get(first.id) == first
        assert reopened.stored_artifacts.get(entity_id(461)) is None
        assert_integrity(reopened)


def test_pr011_rep_009_deterministic_list_ordering(
    repository_environment: RepositoryEnvironment,
) -> None:
    artifacts = (
        prepared(
            473,
            repository_environment.recipes[0].recipe_version_id,
            entity_id(483),
            created_offset=30,
        ),
        prepared(
            471,
            repository_environment.recipes[1].recipe_version_id,
            entity_id(481),
            created_offset=10,
        ),
        prepared(
            472,
            repository_environment.recipes[2].recipe_version_id,
            entity_id(482),
            created_offset=20,
        ),
    )
    with production_uow(repository_environment) as unit:
        for index, (artifact, stored_number) in enumerate(
            zip(artifacts, (483, 481, 482), strict=True)
        ):
            add_complete(unit, artifact, stored_number=stored_number, audit_number=493 - index)
        unit.commit()
    with production_uow(repository_environment) as reopened:
        assert reopened.prepared_image_artifacts.list_by_source(valid_source_file().id) == (
            artifacts[1],
            artifacts[2],
            artifacts[0],
        )
        assert_integrity(reopened)


@pytest.mark.parametrize("mutation", ["update", "delete", "replace"])
def test_pr011_rep_010_immutable_update_delete_replace_rejected(
    repository_environment: RepositoryEnvironment, mutation: str
) -> None:
    first = commit_first(repository_environment)
    with (
        pytest.raises(sqlite3.IntegrityError),
        production_uow(repository_environment) as unit,
    ):
        connection = unit._connection()
        if mutation == "update":
            connection.execute(
                "UPDATE prepared_image_artifacts SET width=2 WHERE prepared_artifact_id=?",
                (str(first.id),),
            )
        elif mutation == "delete":
            connection.execute(
                "DELETE FROM prepared_image_artifacts WHERE prepared_artifact_id=?",
                (str(first.id),),
            )
        else:
            connection.execute(
                "INSERT OR REPLACE INTO prepared_image_artifacts SELECT * "
                "FROM prepared_image_artifacts WHERE prepared_artifact_id=?",
                (str(first.id),),
            )
    with production_uow(repository_environment) as reopened:
        assert reopened.prepared_image_artifacts.get(first.id) == first
        assert_integrity(reopened)


def test_pr011_rep_011_production_uow_close_containment(
    repository_environment: RepositoryEnvironment,
) -> None:
    artifact = prepared(490, repository_environment.recipes[0].recipe_version_id, entity_id(491))
    unit = repository_environment.database.unit_of_work()
    with unit:
        assert_foreign_keys(unit)
        repository = unit.prepared_image_artifacts
        add_complete(unit, artifact, stored_number=491, audit_number=492)
    with pytest.raises(PersistenceError) as property_error:
        _ = unit.prepared_image_artifacts
    assert property_error.value.code is PersistenceErrorCode.UOW_CLOSED
    with pytest.raises(PersistenceError) as repository_error:
        repository.get(artifact.id)
    assert repository_error.value.code is PersistenceErrorCode.UOW_CLOSED
    with production_uow(repository_environment) as reopened:
        assert reopened.prepared_image_artifacts.get(artifact.id) is None
        assert_integrity(reopened)


def test_prepared_artifact_repository_surface_remains_create_once() -> None:
    from document_intake.persistence.database import PreparedImageArtifactRepo

    assert not hasattr(PreparedImageArtifactRepo, "update")
    assert not hasattr(PreparedImageArtifactRepo, "delete")
    assert not hasattr(PreparedImageArtifactRepo, "replace")


def test_public_queries_remain_sql_scoped_until_corruption_stage() -> None:
    from document_intake.persistence.database import PreparedImageArtifactRepo

    source = inspect.getsource(PreparedImageArtifactRepo)
    assert "ORDER BY created_at_utc,prepared_artifact_id" in source
