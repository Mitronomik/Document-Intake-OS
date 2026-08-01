"""Deterministic schema-8 SQLite fixtures for PR-012 persistence evidence."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)
from document_intake.persistence.database import (
    SourceFileRepo,
    StoredArtifactRepo,
    UploadBatchRepo,
)
from document_intake.persistence.repositories.document_regions import DocumentRegionSetRepo
from document_intake.persistence.repositories.image_geometry import ImageGeometryRecipeRepo
from tests.persistence.test_repositories import migrated_connection
from tests.support.pr011 import (
    STAMP,
    actor,
    entity_id,
    valid_original_stored_artifact,
    valid_source_file,
    valid_upload_batch,
)


def schema8_uow(*, second_source: bool = False):
    connection = migrated_connection()
    uow = SimpleNamespace(
        _connection=lambda: connection,
        _invalidate_if_transaction_lost=lambda: None,
        _invalidate=lambda: None,
    )
    uow.upload_batches = UploadBatchRepo(uow)
    uow.stored_artifacts = StoredArtifactRepo(uow)
    uow.source_files = SourceFileRepo(uow)
    uow.image_geometry_recipes = ImageGeometryRecipeRepo(uow)
    uow.document_region_sets = DocumentRegionSetRepo(uow)
    uow.upload_batches.add(valid_upload_batch())
    uow.stored_artifacts.add(valid_original_stored_artifact())
    uow.source_files.add(valid_source_file())
    if second_source:
        artifact = replace(valid_original_stored_artifact(), artifact_id=entity_id(12))
        source = replace(
            valid_source_file(),
            id=entity_id(21),
            original_artifact_id=artifact.artifact_id,
            original_basename=valid_source_file().original_basename.__class__(
                "second-synthetic.jpg"
            ),
        )
        uow.stored_artifacts.add(artifact)
        uow.source_files.add(source)
    connection.commit()
    return connection, uow


def quadrilateral(offset: int = 0) -> SourceQuadrilateral:
    return SourceQuadrilateral(
        GeometryPoint(offset, 0),
        GeometryPoint(16 + offset, 0),
        GeometryPoint(16 + offset, 16),
        GeometryPoint(offset, 16),
    )


def recipe(
    recipe_id: int,
    source_id: int,
    region_id: int,
    revision: int,
    predecessor_id: int | None = None,
    *,
    offset: int = 0,
) -> ImageGeometryRecipe:
    return ImageGeometryRecipe(
        entity_id(recipe_id),
        entity_id(source_id),
        None if predecessor_id is None else entity_id(predecessor_id),
        revision,
        GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
        32,
        24,
        GeometryQuarterTurn.DEG_0,
        quadrilateral(offset),
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        STAMP + timedelta(minutes=recipe_id),
        entity_id(region_id),
    )


def region_set(
    set_id: int,
    source_id: int,
    revision: int,
    predecessor_id: int | None,
    members: tuple[tuple[int, int], ...],
) -> DocumentRegionSetVersion:
    return DocumentRegionSetVersion(
        entity_id(set_id),
        entity_id(source_id),
        None if predecessor_id is None else entity_id(predecessor_id),
        revision,
        tuple(
            DocumentRegionSetMember(order, entity_id(region_id), entity_id(recipe_id))
            for order, (region_id, recipe_id) in enumerate(members, 1)
        ),
        datetime(2026, 7, 27, 12, revision, tzinfo=UTC),
        actor(),
    )


def table_rows(connection: sqlite3.Connection, table: str) -> tuple[tuple[object, ...], ...]:
    return tuple(connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall())
