from __future__ import annotations

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


def memory_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    database._apply_migrations(connection)
    return connection


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


def test_clean_database_migrates_to_schema_version_2_and_history_order() -> None:
    connection = memory_connection()
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    assert connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall() == [
        (1, V0001_MIGRATION.name, V0001_MIGRATION.checksum),
        (2, V0002_MIGRATION.name, V0002_MIGRATION.checksum),
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
