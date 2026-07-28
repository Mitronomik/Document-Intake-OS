from __future__ import annotations

import json
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
from document_intake.persistence.errors import (
    PersistenceError,
    PersistenceErrorCode,
    translate_driver_error,
)
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
    with production_uow(repository_environment) as unit:
        connection = unit._connection()
        with pytest.raises(Exception) as caught:
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
        translated = translate_driver_error(caught.value)
        assert translated.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
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


_UPDATE_TRIGGER = (
    "CREATE TRIGGER prepared_image_artifacts_no_update "
    "BEFORE UPDATE ON prepared_image_artifacts BEGIN "
    "SELECT RAISE(ABORT,'prepared_image_artifacts immutable'); END"
)


def inject_corruption(
    environment: RepositoryEnvironment,
    artifact_id: EntityId,
    column: str,
    value: object,
) -> None:
    connection = database._open_connection(environment.path, Provider())
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DROP TRIGGER prepared_image_artifacts_no_update")
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            f"UPDATE prepared_image_artifacts SET {column}=? WHERE prepared_artifact_id=?",
            (value, str(artifact_id)),
        )
        connection.execute(_UPDATE_TRIGGER)
        connection.execute("COMMIT")
        assert connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='trigger' "
            "AND name='prepared_image_artifacts_no_update'"
        ).fetchone() == (1,)
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def committed_pair(
    environment: RepositoryEnvironment,
) -> tuple[PreparedImageArtifact, PreparedImageArtifact]:
    first = prepared(510, environment.recipes[0].recipe_version_id, entity_id(511))
    second = prepared(
        520, environment.recipes[1].recipe_version_id, entity_id(521), created_offset=1
    )
    with production_uow(environment) as unit:
        add_complete(unit, first, stored_number=511, audit_number=512)
        add_complete(unit, second, stored_number=521, audit_number=522)
        unit.commit()
    return first, second


def assert_corruption_error(action: object) -> None:
    with pytest.raises(PersistenceError) as caught:
        action()  # type: ignore[operator]
    assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
    rendered = f"{caught.value!s} {caught.value!r}"
    assert rendered == (
        "ERR_PERSISTED_DATA_INVALID PersistenceError(code=ERR_PERSISTED_DATA_INVALID)"
    )


def test_pr011_rep_012_scoped_id_query_corruption_behavior(
    repository_environment: RepositoryEnvironment,
) -> None:
    target, unrelated = committed_pair(repository_environment)
    inject_corruption(repository_environment, unrelated.id, "canonical_payload", "not-json")
    with production_uow(repository_environment) as unit:
        assert unit.prepared_image_artifacts.get(target.id) == target
        assert_corruption_error(lambda: unit.prepared_image_artifacts.get(unrelated.id))


def natural_query(unit: SqlCipherUnitOfWork, artifact: PreparedImageArtifact) -> object:
    return unit.prepared_image_artifacts.get_by_natural_key(
        artifact.geometry_recipe_version_id,
        artifact.pipeline_id,
        artifact.pipeline_version,
        artifact.output_contract_id,
        artifact.output_contract_version,
    )


def test_pr011_rep_013_scoped_natural_key_corruption_behavior(
    repository_environment: RepositoryEnvironment,
) -> None:
    target, unrelated = committed_pair(repository_environment)
    inject_corruption(repository_environment, unrelated.id, "canonical_payload", "not-json")
    with production_uow(repository_environment) as unit:
        assert natural_query(unit, target) == target
        assert_corruption_error(lambda: natural_query(unit, unrelated))


def add_alternate_source(
    environment: RepositoryEnvironment,
) -> tuple[object, object, StoredArtifactRecord]:
    original = replace(
        valid_original_stored_artifact(),
        artifact_id=entity_id(601),
        plaintext_sha256="e" * 64,
        ciphertext_sha256="f" * 64,
    )
    source = replace(
        valid_source_file(),
        id=entity_id(602),
        original_artifact_id=original.artifact_id,
        sha256=type(valid_source_file().sha256)(original.plaintext_sha256),
    )
    recipe = replace(
        valid_geometry_recipe(),
        recipe_version_id=entity_id(603),
        region_id=entity_id(603),
        source_file_id=source.id,
    )
    extra_stored = replace(valid_prepared_stored_artifact(), artifact_id=entity_id(604))
    with production_uow(environment) as unit:
        batch = unit.upload_batches.get(valid_upload_batch().id)
        assert batch is not None
        unit.stored_artifacts.add(original)
        unit.source_files.add(source)
        unit.upload_batches.update(batch.append_source_file_id(source.id))
        unit.image_geometry_recipes.add(recipe)
        unit.stored_artifacts.add(extra_stored)
        unit.commit()
    return source, recipe, extra_stored


def test_pr011_rep_014_scoped_source_list_corruption_behavior(
    repository_environment: RepositoryEnvironment,
) -> None:
    source, recipe, _ = add_alternate_source(repository_environment)
    target = prepared(610, repository_environment.recipes[0].recipe_version_id, entity_id(611))
    unrelated = replace(
        prepared(620, recipe.recipe_version_id, entity_id(621), created_offset=1),
        source_file_id=source.id,
    )
    with production_uow(repository_environment) as unit:
        add_complete(unit, target, stored_number=611, audit_number=612)
        add_complete(unit, unrelated, stored_number=621, audit_number=622)
        unit.commit()
    inject_corruption(repository_environment, unrelated.id, "canonical_payload", "not-json")
    with production_uow(repository_environment) as unit:
        assert unit.prepared_image_artifacts.list_by_source(target.source_file_id) == (target,)
        assert_corruption_error(
            lambda: unit.prepared_image_artifacts.list_by_source(unrelated.source_file_id)
        )


def test_pr011_rep_015_scoped_geometry_list_corruption_behavior(
    repository_environment: RepositoryEnvironment,
) -> None:
    target, unrelated = committed_pair(repository_environment)
    inject_corruption(repository_environment, unrelated.id, "canonical_payload", "not-json")
    with production_uow(repository_environment) as unit:
        assert unit.prepared_image_artifacts.list_by_geometry_recipe(
            target.geometry_recipe_version_id
        ) == (target,)
        assert_corruption_error(
            lambda: unit.prepared_image_artifacts.list_by_geometry_recipe(
                unrelated.geometry_recipe_version_id
            )
        )


_PAYLOAD_CASES = (
    "malformed_json",
    "missing_field",
    "extra_field",
    "invalid_prepared_uuid",
    "invalid_source_uuid",
    "invalid_recipe_uuid",
    "invalid_stored_uuid",
    "boolean_integer",
    "pipeline_version",
    "contract_version",
    "media_type",
    "color_space",
    "zero_width",
    "negative_height",
    "byte_size",
    "sha256",
    "jpeg_quality",
    "resize_percent",
    "malformed_datetime",
    "naive_datetime",
    "actor_kind",
    "identity_mismatch",
)


def corrupted_payload(artifact: PreparedImageArtifact, case: str) -> str:
    from document_intake.persistence import serialization

    if case == "malformed_json":
        return "not-json"
    payload = json.loads(serialization.prepared_image_artifact_to_json(artifact))
    if case == "missing_field":
        payload.pop("width")
    elif case == "extra_field":
        payload["unexpected"] = True
    else:
        path, value = {
            "invalid_prepared_uuid": (("id",), "invalid"),
            "invalid_source_uuid": (("source_file_id",), "invalid"),
            "invalid_recipe_uuid": (("geometry_recipe_version_id",), "invalid"),
            "invalid_stored_uuid": (("stored_artifact_id",), "invalid"),
            "boolean_integer": (("width",), True),
            "pipeline_version": (("pipeline_version",), 2),
            "contract_version": (("output_contract_version",), 2),
            "media_type": (("media_type",), "PNG"),
            "color_space": (("color_space",), "RGB"),
            "zero_width": (("width",), 0),
            "negative_height": (("height",), -1),
            "byte_size": (("byte_size",), 0),
            "sha256": (("sha256",), "bad"),
            "jpeg_quality": (("jpeg_quality",), 94),
            "resize_percent": (("resize_percent",), 99),
            "malformed_datetime": (("created_at",), "bad"),
            "naive_datetime": (("created_at",), "2026-07-26T12:00:00"),
            "actor_kind": (("created_by", "kind"), "INVALID"),
            "identity_mismatch": (("id",), str(entity_id(999))),
        }[case]
        if len(path) == 1:
            payload[path[0]] = value
        else:
            payload[path[0]][path[1]] = value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@pytest.mark.parametrize("case", _PAYLOAD_CASES)
def test_pr011_rep_016_canonical_payload_corruption_matrix(
    repository_environment: RepositoryEnvironment, case: str
) -> None:
    artifact = commit_first(repository_environment)
    payload = corrupted_payload(artifact, case)
    inject_corruption(repository_environment, artifact.id, "canonical_payload", payload)
    with production_uow(repository_environment) as unit:
        assert_corruption_error(lambda: unit.prepared_image_artifacts.get(artifact.id))


_PROJECTED_COLUMNS = (
    "prepared_artifact_id",
    "source_file_id",
    "geometry_recipe_version_id",
    "stored_artifact_id",
    "pipeline_id",
    "pipeline_version",
    "output_contract_id",
    "output_contract_version",
    "media_type",
    "color_space",
    "width",
    "height",
    "byte_size",
    "sha256",
    "jpeg_quality",
    "resize_percent",
    "created_at_utc",
    "created_by_id",
    "created_by_kind",
)


@pytest.mark.parametrize("column", _PROJECTED_COLUMNS)
def test_pr011_rep_017_projected_column_mismatch_matrix(
    repository_environment: RepositoryEnvironment, column: str
) -> None:
    source, _, extra_stored = add_alternate_source(repository_environment)
    artifact = commit_first(repository_environment)
    value = {
        "prepared_artifact_id": str(entity_id(901)),
        "source_file_id": str(source.id),
        "geometry_recipe_version_id": str(repository_environment.recipes[1].recipe_version_id),
        "stored_artifact_id": str(extra_stored.artifact_id),
        "pipeline_id": "OTHER",
        "pipeline_version": 2,
        "output_contract_id": "OTHER",
        "output_contract_version": 2,
        "media_type": "PNG",
        "color_space": "RGB",
        "width": artifact.width + 1,
        "height": artifact.height + 1,
        "byte_size": artifact.byte_size + 1,
        "sha256": "d" * 64,
        "jpeg_quality": 94,
        "resize_percent": 99,
        "created_at_utc": "2026-07-26T12:00:01Z",
        "created_by_id": str(entity_id(998)),
        "created_by_kind": "ADMIN",
    }[column]
    inject_corruption(repository_environment, artifact.id, column, value)
    selected_id = entity_id(901) if column == "prepared_artifact_id" else artifact.id
    with production_uow(repository_environment) as unit:
        assert_corruption_error(lambda: unit.prepared_image_artifacts.get(selected_id))
