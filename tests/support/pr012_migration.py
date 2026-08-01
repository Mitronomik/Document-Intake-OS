"""Deterministic synthetic schema-7 fixtures for PR-012 migration evidence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain.entities.imports import SourceFile, UploadBatch
from document_intake.domain.enums import (
    ActorKind,
    ArtifactKind,
    ColorSpace,
    PreparedMediaType,
    SourceMediaType,
    UploadBatchStatus,
)
from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_PIPELINE_ID,
    PreparedImageArtifact,
)
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects import Sha256Digest as PreparedSha256Digest
from document_intake.domain.value_objects.imports import (
    BatchNumber,
    PerceptualHash,
    Sha256Digest,
    SourceBasename,
)
from document_intake.persistence import database, geometry_serialization
from document_intake.persistence.database import (
    PreparedImageArtifactRepo,
    SourceFileRepo,
    StoredArtifactRepo,
    UploadBatchRepo,
)
from document_intake.persistence.migrations import MIGRATIONS

STAMP = datetime(2026, 8, 1, 9, tzinfo=UTC)
SOURCE_A_ID = EntityId.parse("00000000-0000-0000-0000-000000000120")
SOURCE_B_ID = EntityId.parse("00000000-0000-0000-0000-000000000220")
RECIPE_A_IDS = tuple(
    EntityId.parse(f"00000000-0000-0000-0000-{number:012d}") for number in (301, 302, 303)
)
RECIPE_B_IDS = tuple(
    EntityId.parse(f"00000000-0000-0000-0000-{number:012d}") for number in (401, 402)
)
PREPARED_IDS = tuple(
    EntityId.parse(f"00000000-0000-0000-0000-{number:012d}") for number in (310, 312, 411)
)

SNAPSHOT_TABLES = (
    "schema_migrations",
    "upload_batches",
    "upload_batch_source_files",
    "source_files",
    "stored_artifacts",
    "image_geometry_recipes",
    "prepared_image_artifacts",
    "audit_events",
)


class RepositoryUow:
    """Minimal established repository test boundary over a live SQLite connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def _connection(self) -> sqlite3.Connection:
        return self.connection

    def _invalidate_if_transaction_lost(self) -> None:
        return None

    def _invalidate(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class DatabaseSnapshot:
    rows: tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]
    schema_objects: tuple[tuple[Any, ...], ...]
    geometry_table_sql: str


@dataclass(frozen=True, slots=True)
class PopulatedSchema7:
    connection: sqlite3.Connection
    sources: tuple[SourceFile, SourceFile]
    recipes: tuple[ImageGeometryRecipe, ...]
    prepared: tuple[PreparedImageArtifact, ...]
    stored: tuple[StoredArtifactRecord, ...]
    legacy_payloads: tuple[tuple[EntityId, str], ...]
    before: DatabaseSnapshot

    @property
    def source_a_recipes(self) -> tuple[ImageGeometryRecipe, ...]:
        return self.recipes[:3]

    @property
    def source_b_recipes(self) -> tuple[ImageGeometryRecipe, ...]:
        return self.recipes[3:]


def open_schema7(path: Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:" if path is None else path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    for migration in MIGRATIONS[:7]:
        database._apply_one_migration(connection, migration)
    return connection


def _actor() -> ActorRef:
    return ActorRef(EntityId.parse("00000000-0000-0000-0000-000000000090"), ActorKind.SYSTEM)


def _stored(
    number: int, kind: ArtifactKind, marker: str, created_offset: int
) -> StoredArtifactRecord:
    return StoredArtifactRecord(
        EntityId.parse(f"00000000-0000-0000-0000-{number:012d}"),
        kind,
        1,
        100 + number,
        marker * 64,
        marker.upper() * 64,
        1,
        1,
        STAMP + timedelta(minutes=created_offset),
    )


def _source(
    source_number: int,
    batch_number: int,
    original_number: int,
    marker: str,
    width: int,
    height: int,
    imported_offset: int,
) -> tuple[UploadBatch, StoredArtifactRecord, SourceFile]:
    batch_id = EntityId.parse(f"00000000-0000-0000-0000-{batch_number:012d}")
    source_id = EntityId.parse(f"00000000-0000-0000-0000-{source_number:012d}")
    original = _stored(original_number, ArtifactKind.ORIGINAL, marker, imported_offset)
    batch = UploadBatch(
        batch_id,
        BatchNumber(f"BATCH-{batch_number}"),
        STAMP + timedelta(minutes=imported_offset),
        _actor(),
        UploadBatchStatus.NEW,
        (),
    )
    source = SourceFile(
        source_id,
        batch_id,
        original.artifact_id,
        SourceBasename(f"synthetic-source-{marker}.jpg"),
        SourceMediaType.JPEG,
        original.plaintext_length,
        Sha256Digest(original.plaintext_sha256),
        PerceptualHash("DHASH64", 1, 64, marker * 16),
        width,
        height,
        None,
        STAMP + timedelta(minutes=imported_offset),
        _actor(),
    )
    return batch, original, source


def _quadrilateral(offset: int, width: int, height: int) -> SourceQuadrilateral:
    left = 2 + offset
    top = 3 + offset
    right = width - 4 - offset
    bottom = height - 5 - offset
    return SourceQuadrilateral(
        GeometryPoint(left, top),
        GeometryPoint(right, top + 1),
        GeometryPoint(right - 1, bottom),
        GeometryPoint(left + 1, bottom - 1),
    )


def _recipe(
    recipe_id: EntityId,
    source_id: EntityId,
    region_id: EntityId,
    predecessor: EntityId | None,
    revision: int,
    width: int,
    height: int,
    offset: int,
    turn: GeometryQuarterTurn,
) -> ImageGeometryRecipe:
    return ImageGeometryRecipe(
        recipe_id,
        source_id,
        predecessor,
        revision,
        GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
        width,
        height,
        turn,
        _quadrilateral(offset, width, height),
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        STAMP + timedelta(minutes=10 + offset),
        region_id,
    )


def _legacy_payload(recipe: ImageGeometryRecipe) -> str:
    payload = json.loads(geometry_serialization.image_geometry_recipe_to_json(recipe))
    del payload["region_id"]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _insert_legacy_recipe(connection: sqlite3.Connection, recipe: ImageGeometryRecipe) -> str:
    columns = geometry_serialization.image_geometry_recipe_columns(recipe)
    payload = _legacy_payload(recipe)
    connection.execute(
        "INSERT INTO image_geometry_recipes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*(columns[0], columns[1], *columns[3:]), payload),
    )
    return payload


def _prepared(
    prepared_id: EntityId,
    source_id: EntityId,
    recipe_id: EntityId,
    stored: StoredArtifactRecord,
    offset: int,
) -> PreparedImageArtifact:
    return PreparedImageArtifact(
        prepared_id,
        source_id,
        recipe_id,
        stored.artifact_id,
        PREPARED_JPEG_PIPELINE_ID,
        1,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        1,
        PreparedMediaType.JPEG,
        ColorSpace.SRGB,
        40 + offset,
        30 + offset,
        stored.plaintext_length,
        PreparedSha256Digest(stored.plaintext_sha256),
        (95, 90, 85)[offset],
        (100, 90, 80)[offset],
        STAMP + timedelta(minutes=30 + offset),
        _actor(),
    )


def capture_snapshot(connection: sqlite3.Connection) -> DatabaseSnapshot:
    rows = tuple(
        (
            table,
            tuple(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()),
        )
        for table in SNAPSHOT_TABLES
    )
    schema_objects = tuple(
        connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()
    )
    geometry_table_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='image_geometry_recipes'"
    ).fetchone()[0]
    return DatabaseSnapshot(rows, schema_objects, geometry_table_sql)


def build_populated_schema7(path: Path | None = None) -> PopulatedSchema7:
    connection = open_schema7(path)
    uow = RepositoryUow(connection)
    batches_and_sources = (
        _source(120, 101, 111, "1", 101, 83, 1),
        _source(220, 201, 211, "2", 137, 109, 2),
    )
    sources: list[SourceFile] = []
    stored: list[StoredArtifactRecord] = []
    for batch, original, source in batches_and_sources:
        UploadBatchRepo(uow).add(batch)
        StoredArtifactRepo(uow).add(original)
        SourceFileRepo(uow).add(source)
        UploadBatchRepo(uow).update(batch.append_source_file_id(source.id))
        sources.append(source)
        stored.append(original)

    a1, a2, a3 = (
        _recipe(
            RECIPE_A_IDS[0],
            SOURCE_A_ID,
            RECIPE_A_IDS[0],
            None,
            1,
            101,
            83,
            0,
            GeometryQuarterTurn.DEG_0,
        ),
        _recipe(
            RECIPE_A_IDS[1],
            SOURCE_A_ID,
            RECIPE_A_IDS[0],
            RECIPE_A_IDS[0],
            2,
            101,
            83,
            1,
            GeometryQuarterTurn.DEG_90,
        ),
        _recipe(
            RECIPE_A_IDS[2],
            SOURCE_A_ID,
            RECIPE_A_IDS[0],
            RECIPE_A_IDS[1],
            3,
            101,
            83,
            2,
            GeometryQuarterTurn.DEG_180,
        ),
    )
    b1, b2 = (
        _recipe(
            RECIPE_B_IDS[0],
            SOURCE_B_ID,
            RECIPE_B_IDS[0],
            None,
            1,
            137,
            109,
            4,
            GeometryQuarterTurn.DEG_270,
        ),
        _recipe(
            RECIPE_B_IDS[1],
            SOURCE_B_ID,
            RECIPE_B_IDS[0],
            RECIPE_B_IDS[0],
            2,
            137,
            109,
            5,
            GeometryQuarterTurn.DEG_0,
        ),
    )
    recipes = (a1, a2, a3, b1, b2)
    legacy_payloads = tuple(
        (recipe.recipe_version_id, _insert_legacy_recipe(connection, recipe)) for recipe in recipes
    )

    prepared_stored = (
        _stored(311, ArtifactKind.PREPARED_JPEG, "3", 31),
        _stored(313, ArtifactKind.PREPARED_JPEG, "4", 32),
        _stored(412, ArtifactKind.PREPARED_JPEG, "5", 33),
    )
    prepared = (
        _prepared(PREPARED_IDS[0], SOURCE_A_ID, RECIPE_A_IDS[0], prepared_stored[0], 0),
        _prepared(PREPARED_IDS[1], SOURCE_A_ID, RECIPE_A_IDS[2], prepared_stored[1], 1),
        _prepared(PREPARED_IDS[2], SOURCE_B_ID, RECIPE_B_IDS[1], prepared_stored[2], 2),
    )
    prepared_repository = PreparedImageArtifactRepo(uow)
    stored_repository = StoredArtifactRepo(uow)
    for record, artifact in zip(prepared_stored, prepared, strict=True):
        stored_repository.add(record)
        prepared_repository.add(artifact)
    stored.extend(prepared_stored)
    return PopulatedSchema7(
        connection,
        (sources[0], sources[1]),
        recipes,
        prepared,
        tuple(stored),
        legacy_payloads,
        capture_snapshot(connection),
    )


def history(connection: sqlite3.Connection) -> list[tuple[Any, ...]]:
    return connection.execute(
        "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
    ).fetchall()


def schema_object_names(connection: sqlite3.Connection) -> tuple[tuple[str, str], ...]:
    return tuple(
        connection.execute(
            "SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()
    )
