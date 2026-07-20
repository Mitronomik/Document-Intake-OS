from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain.entities.imports import SourceFile, UploadBatch
from document_intake.domain.enums import ActorKind, ArtifactKind, SourceMediaType, UploadBatchStatus
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import (
    BatchNumber,
    PerceptualHash,
    Sha256Digest,
    SourceBasename,
)
from document_intake.persistence import database, serialization
from document_intake.persistence.database import SqlCipherUnitOfWork
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.persistence.test_unit_of_work import Provider, migrated_file, open_sqlite

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def actor(value: int = 900) -> ActorRef:
    return ActorRef(eid(value), ActorKind.OPERATOR)


def batch(
    value: int, number: str | None = None, source_ids: tuple[EntityId, ...] = ()
) -> UploadBatch:
    return UploadBatch(
        eid(value),
        BatchNumber(number or f"BATCH-{value}"),
        NOW,
        actor(),
        UploadBatchStatus.NEW,
        source_ids,
    )


def artifact(value: int, created_at: datetime = NOW) -> StoredArtifactRecord:
    return StoredArtifactRecord(
        artifact_id=eid(value),
        artifact_kind=ArtifactKind.ORIGINAL,
        object_generation=1,
        plaintext_length=12,
        plaintext_sha256="a" * 64,
        ciphertext_sha256="b" * 64,
        key_version=1,
        storage_format_version=1,
        created_at=created_at,
    )


def source(
    value: int,
    *,
    batch_value: int = 100,
    artifact_value: int | None = None,
    imported_at: datetime = NOW,
    sha: str = "c" * 64,
    phash: str = "0000000000000000",
) -> SourceFile:
    return SourceFile(
        id=eid(value),
        batch_id=eid(batch_value),
        original_artifact_id=eid(artifact_value or value + 1000),
        original_basename=SourceBasename(f"synthetic-{value}.jpg"),
        detected_media_type=SourceMediaType.JPEG,
        byte_size=12,
        sha256=Sha256Digest(sha),
        perceptual_hash=PerceptualHash("DHASH64", 1, 64, phash),
        width=32,
        height=24,
        exif_orientation=None,
        imported_at=imported_at,
        imported_by=actor(),
    )


def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "source-import.db"
    migrated_file(path)
    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    return path


def add_source(uow: SqlCipherUnitOfWork, value: SourceFile) -> None:
    uow.stored_artifacts.add(artifact(value.original_artifact_id.value.int, value.imported_at))
    uow.source_files.add(value)
    current = uow.upload_batches.get(value.batch_id)
    assert current is not None
    uow.upload_batches.update(current.append_source_file_id(value.id))


def test_upload_batch_add_get_get_by_number_and_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = db_path(tmp_path, monkeypatch)
    first = batch(100)
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(first)
        assert uow.upload_batches.get(first.id) == first
        assert uow.upload_batches.get_by_number(first.number) == first
        assert uow.upload_batches.get(eid(999)) is None
        uow.commit()
    for duplicate in (first, batch(101, first.number.value)):
        with SqlCipherUnitOfWork(path, Provider()) as uow:
            with pytest.raises(PersistenceError) as caught:
                uow.upload_batches.add(duplicate)
            assert caught.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS


def test_source_file_add_get_lists_order_and_compatible_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = db_path(tmp_path, monkeypatch)
    earlier_high_id = source(20, imported_at=NOW - timedelta(minutes=1), sha="d" * 64)
    same_time_high_id = source(30, sha="d" * 64, phash="0000000000000001")
    same_time_low_id = source(10, sha="e" * 64, phash="0000000000000002")
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(batch(100))
        for value in (same_time_high_id, earlier_high_id, same_time_low_id):
            add_source(uow, value)
        assert uow.source_files.get(earlier_high_id.id) == earlier_high_id
        assert uow.source_files.list_by_batch(eid(100)) == (
            earlier_high_id,
            same_time_low_id,
            same_time_high_id,
        )
        assert uow.source_files.list_by_sha256(Sha256Digest("d" * 64)) == (
            earlier_high_id,
            same_time_high_id,
        )
        assert uow.source_files.list_compatible_perceptual_hashes("DHASH64", 1, 64) == (
            earlier_high_id,
            same_time_low_id,
            same_time_high_id,
        )
        assert uow.source_files.list_compatible_perceptual_hashes("DHASH64", 2, 64) == ()
        uow.commit()


def test_duplicate_source_and_artifact_ids_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = db_path(tmp_path, monkeypatch)
    first = source(1)
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(batch(100))
        add_source(uow, first)
        uow.commit()
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        with pytest.raises(PersistenceError) as duplicate_source:
            uow.source_files.add(first)
        assert duplicate_source.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
        second = source(2, artifact_value=1001)
        with pytest.raises(PersistenceError) as duplicate_artifact:
            uow.source_files.add(second)
        assert duplicate_artifact.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS


def test_batch_update_is_append_only_and_immutable_fields_cannot_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = db_path(tmp_path, monkeypatch)
    original = batch(100)
    first = source(1)
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(original)
        uow.stored_artifacts.add(artifact(1001))
        uow.source_files.add(first)
        uow.upload_batches.update(original.append_source_file_id(first.id))
        persisted = uow.upload_batches.get(original.id)
        assert persisted is not None
        for invalid in (
            replace(persisted, number=BatchNumber("CHANGED")),
            replace(persisted, created_at=NOW + timedelta(seconds=1)),
            replace(persisted, created_by=actor(901)),
            replace(persisted, source_file_ids=()),
        ):
            with pytest.raises(PersistenceError) as caught:
                uow.upload_batches.update(invalid)
            assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
        assert not hasattr(uow.source_files, "update")
        assert not hasattr(uow.source_files, "delete")
        assert not hasattr(uow.upload_batches, "delete")


def test_missing_source_cross_batch_membership_and_duplicate_membership_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = db_path(tmp_path, monkeypatch)
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        first = batch(100)
        second = batch(200)
        uow.upload_batches.add(first)
        uow.upload_batches.add(second)
        with pytest.raises(PersistenceError) as missing:
            uow.upload_batches.update(first.append_source_file_id(eid(1)))
        assert missing.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
        other = source(2, batch_value=200)
        uow.stored_artifacts.add(artifact(1002))
        uow.source_files.add(other)
        with pytest.raises(PersistenceError) as cross_batch:
            uow.upload_batches.update(first.append_source_file_id(other.id))
        assert cross_batch.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
        uow.upload_batches.update(second.append_source_file_id(other.id))
        persisted = uow.upload_batches.get(second.id)
        assert persisted is not None
        with pytest.raises(InvalidValueError):
            persisted.append_source_file_id(other.id)


@pytest.mark.parametrize(
    "payload_mutation",
    [
        lambda data: data.pop("width"),
        lambda data: data.update({"extra": True}),
        lambda data: data.update({"byte_size": True}),
        lambda data: data.update({"detected_media_type": "BMP"}),
    ],
)
def test_canonical_payload_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload_mutation,  # type: ignore[no-untyped-def]
) -> None:
    path = db_path(tmp_path, monkeypatch)
    value = source(1)
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(batch(100))
        add_source(uow, value)
        uow.commit()
    raw = sqlite3.connect(path, isolation_level=None)
    data = json.loads(raw.execute("SELECT canonical_payload FROM source_files").fetchone()[0])
    payload_mutation(data)
    raw.execute(
        "UPDATE source_files SET canonical_payload=? WHERE id=?",
        (json.dumps(data, sort_keys=True, separators=(",", ":")), str(value.id)),
    )
    raw.close()
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        with pytest.raises(PersistenceError) as caught:
            uow.source_files.get(value.id)
        assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


@pytest.mark.parametrize(
    ("column", "replacement"),
    [
        ("byte_size", 99),
        ("sha256", "f" * 64),
        ("width", 999),
        ("perceptual_hex_value", "f" * 16),
    ],
)
def test_projection_tampering_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    column: str,
    replacement: object,
) -> None:
    path = db_path(tmp_path, monkeypatch)
    value = source(1)
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(batch(100))
        add_source(uow, value)
        uow.commit()
    raw = sqlite3.connect(path, isolation_level=None)
    raw.execute(f"UPDATE source_files SET {column}=? WHERE id=?", (replacement, str(value.id)))
    raw.close()
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        with pytest.raises(PersistenceError) as caught:
            uow.source_files.get(value.id)
        assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_membership_tampering_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = db_path(tmp_path, monkeypatch)
    value = source(1)
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(batch(100))
        add_source(uow, value)
        uow.commit()
    raw = sqlite3.connect(path, isolation_level=None)
    raw.execute("UPDATE upload_batch_source_files SET order_index=9")
    raw.close()
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        with pytest.raises(PersistenceError) as caught:
            uow.upload_batches.get(eid(100))
        assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_transaction_commit_and_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = db_path(tmp_path, monkeypatch)
    committed = batch(100)
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(committed)
        uow.commit()
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        uow.upload_batches.add(batch(200))
        uow.rollback()
    with SqlCipherUnitOfWork(path, Provider()) as uow:
        assert uow.upload_batches.get(committed.id) == committed
        assert uow.upload_batches.get(eid(200)) is None


def test_serializers_round_trip_canonical_values() -> None:
    batch_value = batch(100)
    source_value = source(1)
    assert (
        serialization.upload_batch_from_json(serialization.upload_batch_to_json(batch_value))
        == batch_value
    )
    assert (
        serialization.source_file_from_json(serialization.source_file_to_json(source_value))
        == source_value
    )
