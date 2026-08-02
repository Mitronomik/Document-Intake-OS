"""Deterministic schema-9 PR-013 persistence helpers."""

from __future__ import annotations

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
from document_intake.persistence.repositories.document_side_compositions import (
    DocumentSideCompositionRepo,
)
from tests.support.pr011 import (
    STAMP,
    actor,
    correlation_id,
    entity_id,
    valid_prepared_stored_artifact,
)
from tests.support.pr012_persistence import recipe, region_set, schema8_uow


def schema9_uow():
    connection, uow = schema8_uow(second_source=True)
    uow.document_side_compositions = DocumentSideCompositionRepo(uow)
    first_recipe = recipe(30, 20, 30, 1)
    second_recipe = recipe(31, 21, 31, 1)
    uow.image_geometry_recipes.add(first_recipe)
    uow.image_geometry_recipes.add(second_recipe)
    uow.document_region_sets.add(region_set(60, 20, 1, None, ((30, 30),)))
    uow.document_region_sets.add(region_set(61, 21, 1, None, ((31, 31),)))
    connection.commit()
    return connection, uow


def records(*, swapped: bool = False):
    side_1 = (entity_id(60), entity_id(20), entity_id(30), entity_id(30))
    side_2 = (entity_id(61), entity_id(21), entity_id(31), entity_id(31))
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
