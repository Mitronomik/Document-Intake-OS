"""Deterministic schema-9 PR-013 persistence helpers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.document_side_composition import (
    DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID,
    DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION,
    DocumentSideComposition,
    DocumentSideCompositionVersion,
    PreparedCompositionArtifact,
)
from document_intake.domain.enums import (
    ColorSpace,
    DocumentSideCompositionLayout,
    PreparedMediaType,
)
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    PREPARED_JPEG_PIPELINE_ID,
    PREPARED_JPEG_PIPELINE_VERSION,
)
from document_intake.domain.value_objects import Sha256Digest
from document_intake.persistence import database
from document_intake.persistence.database import AuditEventRepo
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.repositories.document_regions import DocumentRegionSetRepo
from document_intake.persistence.repositories.document_side_compositions import (
    DocumentSideCompositionRepo,
)
from document_intake.persistence.repositories.image_geometry import ImageGeometryRecipeRepo
from tests.support.pr011 import (
    STAMP,
    actor,
    correlation_id,
    entity_id,
    valid_audit_event,
    valid_prepared_stored_artifact,
)
from tests.support.pr012_migration import RepositoryUow, build_populated_schema7
from tests.support.pr012_persistence import recipe, region_set, schema8_uow

Variant = str
SCHEMA8_PRESERVED_TABLES = (
    "upload_batches",
    "upload_batch_source_files",
    "stored_artifacts",
    "source_files",
    "image_geometry_recipes",
    "prepared_image_artifacts",
    "document_region_set_versions",
    "document_region_set_members",
    "audit_events",
)


@dataclass(frozen=True, slots=True)
class PopulatedSchema8:
    connection: sqlite3.Connection
    rows: tuple[tuple[str, tuple[tuple[object, ...], ...]], ...]
    history: tuple[tuple[object, ...], ...]


def snapshot_schema8_rows(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, tuple[tuple[object, ...], ...]], ...]:
    return tuple(
        (
            table,
            tuple(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()),
        )
        for table in SCHEMA8_PRESERVED_TABLES
    )


def build_populated_schema8(path: Path | None = None) -> PopulatedSchema8:
    fixture = build_populated_schema7(path)
    connection = fixture.connection
    database._apply_one_migration(connection, MIGRATIONS[7])
    uow = RepositoryUow(connection)
    uow.image_geometry_recipes = ImageGeometryRecipeRepo(uow)  # type: ignore[attr-defined]
    selected_recipe = fixture.recipes[2]
    confirmed = DocumentRegionSetVersion(
        entity_id(601),
        fixture.sources[0].id,
        None,
        1,
        (DocumentRegionSetMember(1, selected_recipe.region_id, selected_recipe.recipe_version_id),),
        STAMP,
        actor(),
    )
    DocumentRegionSetRepo(uow).add(confirmed)
    AuditEventRepo(uow).add(valid_audit_event())
    assert connection.execute("PRAGMA user_version").fetchone() == (8,)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    return PopulatedSchema8(
        connection,
        snapshot_schema8_rows(connection),
        tuple(
            connection.execute(
                "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
            ).fetchall()
        ),
    )


def schema9_uow(*, variant: Variant = "different_sources", lineage_matrix: bool = False):
    connection, uow = schema8_uow(second_source=variant == "different_sources" or lineage_matrix)
    uow.document_side_compositions = DocumentSideCompositionRepo(uow)
    first_recipe = recipe(30, 20, 30, 1)
    second_source = 21 if variant == "different_sources" or lineage_matrix else 20
    second_recipe = recipe(31, second_source, 31, 1)
    uow.image_geometry_recipes.add(first_recipe)
    uow.image_geometry_recipes.add(second_recipe)
    first_members = ((30, 30), (31, 31)) if variant == "same_region_set" else ((30, 30),)
    uow.document_region_sets.add(region_set(60, 20, 1, None, first_members))
    if variant != "same_region_set":
        revision = 1 if second_source == 21 else 2
        predecessor = None if second_source == 21 else 60
        uow.document_region_sets.add(
            region_set(61, second_source, revision, predecessor, ((31, 31),))
        )
    if lineage_matrix:
        uow.image_geometry_recipes.add(recipe(32, 20, 32, 1))
        for set_id, revision, predecessor in ((62, 2, 60), (63, 3, 62), (64, 4, 63)):
            connection.execute(
                "INSERT INTO document_region_set_versions VALUES(?,?,?,?,?,?,?,?)",
                (
                    str(entity_id(set_id)),
                    str(entity_id(20)),
                    str(entity_id(predecessor)),
                    revision,
                    STAMP.isoformat().replace("+00:00", "Z"),
                    str(actor().actor_id),
                    actor().kind.value,
                    "{}",
                ),
            )
        for set_id, members in (
            (62, ((31, 31),)),
            (63, ((32, 30),)),
            (64, ((30, 30), (32, 32))),
        ):
            for order, (region_id, recipe_id) in enumerate(members, 1):
                connection.execute(
                    "INSERT INTO document_region_set_members VALUES(?,?,?,?)",
                    (
                        str(entity_id(set_id)),
                        order,
                        str(entity_id(region_id)),
                        str(entity_id(recipe_id)),
                    ),
                )
    connection.commit()
    return connection, uow


def records(*, variant: Variant = "different_sources", swapped: bool = False):
    side_1 = (entity_id(60), entity_id(20), entity_id(30), entity_id(30))
    side_2 = (
        entity_id(60 if variant == "same_region_set" else 61),
        entity_id(21 if variant == "different_sources" else 20),
        entity_id(31),
        entity_id(31),
    )
    if swapped:
        side_1, side_2 = side_2, side_1
    composition = DocumentSideComposition(entity_id(101))
    version = DocumentSideCompositionVersion(
        entity_id(102),
        composition.id,
        *side_1,
        *side_2,
        DocumentSideCompositionLayout.VERTICAL,
        4,
        2,
        DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID,
        DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION,
        PREPARED_JPEG_PIPELINE_ID,
        PREPARED_JPEG_PIPELINE_VERSION,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
        STAMP,
        actor(),
        correlation_id(),
    )
    stored = valid_prepared_stored_artifact()
    stored = stored.__class__(
        entity_id(104),
        stored.artifact_kind,
        1,
        stored.plaintext_length,
        stored.plaintext_sha256,
        stored.ciphertext_sha256,
        stored.key_version,
        stored.storage_format_version,
        STAMP,
    )
    artifact = PreparedCompositionArtifact(
        entity_id(103),
        version.id,
        stored.artifact_id,
        PREPARED_JPEG_PIPELINE_ID,
        PREPARED_JPEG_PIPELINE_VERSION,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
        PreparedMediaType.JPEG,
        ColorSpace.SRGB,
        32,
        48,
        stored.plaintext_length,
        Sha256Digest(stored.plaintext_sha256),
        95,
        100,
        STAMP,
        actor(),
    )
    return composition, version, artifact, stored


def natural_kwargs(version):
    return {
        "side_1_region_set_version_id": version.side_1_region_set_version_id,
        "side_1_source_file_id": version.side_1_source_file_id,
        "side_1_region_id": version.side_1_region_id,
        "side_1_geometry_recipe_version_id": version.side_1_geometry_recipe_version_id,
        "side_2_region_set_version_id": version.side_2_region_set_version_id,
        "side_2_source_file_id": version.side_2_source_file_id,
        "side_2_region_id": version.side_2_region_id,
        "side_2_geometry_recipe_version_id": version.side_2_geometry_recipe_version_id,
        "layout": version.layout,
        "outer_margin_px": version.outer_margin_px,
        "inter_side_gap_px": version.inter_side_gap_px,
        "composition_pipeline_id": version.composition_pipeline_id,
        "composition_pipeline_version": version.composition_pipeline_version,
        "jpeg_pipeline_id": version.jpeg_pipeline_id,
        "jpeg_pipeline_version": version.jpeg_pipeline_version,
        "output_contract_id": version.output_contract_id,
        "output_contract_version": version.output_contract_version,
    }
