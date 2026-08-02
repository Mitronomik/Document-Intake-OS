from dataclasses import fields, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

import pytest

from document_intake.application.dto.document_side_composition import (
    CreateDocumentSideCompositionCommand,
    CreateDocumentSideCompositionResult,
    DocumentSideReference,
)
from document_intake.domain.document_side_composition import (
    DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID,
    DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION,
    DocumentSideComposition,
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
    DocumentSideCompositionPipelineVersion,
    DocumentSideCompositionVersion,
    PreparedCompositionArtifact,
)
from document_intake.domain.enums import ActorKind, DocumentSideCompositionLayout
from document_intake.domain.value_objects import ActorRef, EntityId


def entity_id(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def actor() -> ActorRef:
    return ActorRef(entity_id(1), ActorKind.OPERATOR)


def command() -> CreateDocumentSideCompositionCommand:
    return CreateDocumentSideCompositionCommand(
        entity_id(101),
        entity_id(102),
        DocumentSideReference(entity_id(11), entity_id(20), entity_id(30), entity_id(30)),
        DocumentSideReference(entity_id(12), entity_id(21), entity_id(31), entity_id(31)),
        DocumentSideCompositionLayout.VERTICAL,
        16,
        8,
        entity_id(103),
        entity_id(104),
        entity_id(105),
        datetime(2026, 8, 2, tzinfo=UTC),
        actor(),
        entity_id(106),
    )


def test_exact_contract_fields_constants_layout_and_errors() -> None:
    assert DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID == "PILLOW_DOCUMENT_SIDE_COMPOSITION_BICUBIC"
    assert DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION == 1
    assert tuple(DocumentSideCompositionLayout) == (
        DocumentSideCompositionLayout.VERTICAL,
        DocumentSideCompositionLayout.HORIZONTAL,
    )
    assert issubclass(DocumentSideCompositionLayout, StrEnum)
    assert tuple(field.name for field in fields(DocumentSideComposition)) == ("id",)
    assert tuple(field.name for field in fields(DocumentSideReference)) == (
        "region_set_version_id",
        "source_file_id",
        "region_id",
        "geometry_recipe_version_id",
    )
    assert tuple(field.name for field in fields(CreateDocumentSideCompositionResult)) == (
        "composition_version",
        "artifact",
    )
    assert {item.value for item in DocumentSideCompositionErrorCode} == {
        "COMPOSITION_INPUT_COUNT_INVALID",
        "COMPOSITION_INPUT_DUPLICATE",
        "COMPOSITION_ORDER_INVALID",
        "COMPOSITION_LAYOUT_INVALID",
        "COMPOSITION_MARGIN_INVALID",
        "COMPOSITION_GAP_INVALID",
        "REGION_NOT_FOUND",
        "REGION_SET_NOT_FOUND",
        "REGION_SELECTION_INVALID",
        "GEOMETRY_RECIPE_NOT_FOUND",
        "GEOMETRY_RECIPE_INVALID",
        "SOURCE_FILE_NOT_FOUND",
        "ORIGINAL_ARTIFACT_NOT_FOUND",
        "ORIGINAL_BYTES_INVALID",
        "SOURCE_DIMENSIONS_MISMATCH",
        "GEOMETRY_RENDER_FAILED",
        "COMPOSITION_RENDER_FAILED",
        "JPEG_ENCODING_FAILED",
        "SIZE_LIMIT_UNREACHABLE",
        "IDENTITY_CONFLICT",
        "COMPOSITION_ALREADY_EXISTS",
        "STORAGE_PUBLICATION_FAILED",
        "PERSISTENCE_CONFLICT",
        "PERSISTENCE_FAILED",
        "COMMIT_FAILED",
        "PERSISTED_DATA_INVALID",
    }


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"outer_margin_px": True}, "COMPOSITION_MARGIN_INVALID"),
        ({"outer_margin_px": 257}, "COMPOSITION_MARGIN_INVALID"),
        ({"inter_side_gap_px": False}, "COMPOSITION_GAP_INVALID"),
        ({"inter_side_gap_px": -1}, "COMPOSITION_GAP_INVALID"),
        ({"created_at": datetime(2026, 8, 2)}, "COMPOSITION_ORDER_INVALID"),
    ],
)
def test_command_fails_closed(change: dict[str, object], code: str) -> None:
    with pytest.raises(DocumentSideCompositionError) as captured:
        replace(command(), **change)
    assert captured.value.code.value == code
    assert repr(captured.value) == f"DocumentSideCompositionError({code})"


def test_duplicate_lineage_and_created_ids_are_rejected() -> None:
    value = command()
    with pytest.raises(DocumentSideCompositionError) as duplicate:
        replace(
            value,
            side_2=replace(
                value.side_2,
                source_file_id=value.side_1.source_file_id,
                region_id=value.side_1.region_id,
            ),
        )
    assert duplicate.value.code is DocumentSideCompositionErrorCode.COMPOSITION_INPUT_DUPLICATE
    with pytest.raises(DocumentSideCompositionError) as identity:
        replace(value, stored_artifact_id=value.composition_id)
    assert identity.value.code is DocumentSideCompositionErrorCode.IDENTITY_CONFLICT


def test_pipeline_identity_is_fixed_and_records_have_no_revision_fields() -> None:
    assert DocumentSideCompositionPipelineVersion() == DocumentSideCompositionPipelineVersion(
        DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID, 1
    )
    with pytest.raises(DocumentSideCompositionError):
        DocumentSideCompositionPipelineVersion("OTHER", 1)
    version_names = {field.name for field in fields(DocumentSideCompositionVersion)}
    assert (
        not {
            "revision",
            "superseded_composition_version_id",
            "latest_composition_version_id",
            "current_composition_version_id",
        }
        & version_names
    )
    artifact_names = tuple(field.name for field in fields(PreparedCompositionArtifact))
    assert artifact_names[-5:] == (
        "sha256",
        "jpeg_quality",
        "resize_percent",
        "created_at",
        "created_by",
    )
