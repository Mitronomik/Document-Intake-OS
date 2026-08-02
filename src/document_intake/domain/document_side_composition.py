"""Immutable deterministic document-side composition contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from document_intake.domain.enums import (
    ColorSpace,
    DocumentSideCompositionLayout,
    PreparedMediaType,
)
from document_intake.domain.value_objects import ActorRef, EntityId, Sha256Digest

DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID = "PILLOW_DOCUMENT_SIDE_COMPOSITION_BICUBIC"
DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION = 1


class DocumentSideCompositionErrorCode(StrEnum):
    COMPOSITION_INPUT_COUNT_INVALID = "COMPOSITION_INPUT_COUNT_INVALID"
    COMPOSITION_INPUT_DUPLICATE = "COMPOSITION_INPUT_DUPLICATE"
    COMPOSITION_ORDER_INVALID = "COMPOSITION_ORDER_INVALID"
    COMPOSITION_LAYOUT_INVALID = "COMPOSITION_LAYOUT_INVALID"
    COMPOSITION_MARGIN_INVALID = "COMPOSITION_MARGIN_INVALID"
    COMPOSITION_GAP_INVALID = "COMPOSITION_GAP_INVALID"
    REGION_NOT_FOUND = "REGION_NOT_FOUND"
    REGION_SET_NOT_FOUND = "REGION_SET_NOT_FOUND"
    REGION_SELECTION_INVALID = "REGION_SELECTION_INVALID"
    GEOMETRY_RECIPE_NOT_FOUND = "GEOMETRY_RECIPE_NOT_FOUND"
    GEOMETRY_RECIPE_INVALID = "GEOMETRY_RECIPE_INVALID"
    SOURCE_FILE_NOT_FOUND = "SOURCE_FILE_NOT_FOUND"
    ORIGINAL_ARTIFACT_NOT_FOUND = "ORIGINAL_ARTIFACT_NOT_FOUND"
    ORIGINAL_BYTES_INVALID = "ORIGINAL_BYTES_INVALID"
    SOURCE_DIMENSIONS_MISMATCH = "SOURCE_DIMENSIONS_MISMATCH"
    GEOMETRY_RENDER_FAILED = "GEOMETRY_RENDER_FAILED"
    COMPOSITION_RENDER_FAILED = "COMPOSITION_RENDER_FAILED"
    JPEG_ENCODING_FAILED = "JPEG_ENCODING_FAILED"
    SIZE_LIMIT_UNREACHABLE = "SIZE_LIMIT_UNREACHABLE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    COMPOSITION_ALREADY_EXISTS = "COMPOSITION_ALREADY_EXISTS"
    STORAGE_PUBLICATION_FAILED = "STORAGE_PUBLICATION_FAILED"
    PERSISTENCE_CONFLICT = "PERSISTENCE_CONFLICT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    COMMIT_FAILED = "COMMIT_FAILED"
    PERSISTED_DATA_INVALID = "PERSISTED_DATA_INVALID"


class DocumentSideCompositionError(Exception):
    def __init__(self, code: DocumentSideCompositionErrorCode) -> None:
        self.code = code
        super().__init__(code.value)

    def __repr__(self) -> str:
        return f"DocumentSideCompositionError({self.code.value})"


@dataclass(frozen=True, slots=True)
class DocumentSideCompositionPipelineVersion:
    pipeline_id: str = DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID
    version: int = DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION

    def __post_init__(self) -> None:
        if (self.pipeline_id, self.version) != (
            DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID,
            DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION,
        ):
            raise DocumentSideCompositionError(
                DocumentSideCompositionErrorCode.COMPOSITION_RENDER_FAILED
            )


def _require_ids(values: tuple[object, ...]) -> None:
    if not all(isinstance(value, EntityId) for value in values):
        raise DocumentSideCompositionError(DocumentSideCompositionErrorCode.IDENTITY_CONFLICT)


def _require_utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise DocumentSideCompositionError(DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID)


def _artifact_identity_valid(value: PreparedCompositionArtifact) -> bool:
    from document_intake.domain.prepared_jpeg import (
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
        PREPARED_JPEG_PIPELINE_ID,
        PREPARED_JPEG_PIPELINE_VERSION,
    )

    return (
        (value.pipeline_id, value.pipeline_version)
        == (PREPARED_JPEG_PIPELINE_ID, PREPARED_JPEG_PIPELINE_VERSION)
        and (value.output_contract_id, value.output_contract_version)
        == (PREPARED_JPEG_OUTPUT_CONTRACT_ID, PREPARED_JPEG_OUTPUT_CONTRACT_VERSION)
        and value.media_type is PreparedMediaType.JPEG
        and value.color_space is ColorSpace.SRGB
    )


def _artifact_dimensions_valid(value: PreparedCompositionArtifact) -> bool:
    from document_intake.domain.prepared_jpeg import MAX_PREPARED_JPEG_BYTES

    return (
        type(value.width) is int
        and value.width > 0
        and type(value.height) is int
        and value.height > 0
        and type(value.byte_size) is int
        and 1 <= value.byte_size <= MAX_PREPARED_JPEG_BYTES
        and isinstance(value.sha256, Sha256Digest)
    )


def _artifact_quality_valid(value: PreparedCompositionArtifact) -> bool:
    from document_intake.domain.prepared_jpeg import (
        JPEG_QUALITY_SEQUENCE,
        JPEG_RESIZE_PERCENT_SEQUENCE,
    )

    return (
        value.jpeg_quality in JPEG_QUALITY_SEQUENCE
        and value.resize_percent in JPEG_RESIZE_PERCENT_SEQUENCE
        and isinstance(value.created_by, ActorRef)
    )


@dataclass(frozen=True, slots=True)
class DocumentSideComposition:
    id: EntityId

    def __post_init__(self) -> None:
        _require_ids((self.id,))


@dataclass(frozen=True, slots=True)
class DocumentSideCompositionVersion:
    id: EntityId
    composition_id: EntityId
    side_1_region_set_version_id: EntityId
    side_1_source_file_id: EntityId
    side_1_region_id: EntityId
    side_1_geometry_recipe_version_id: EntityId
    side_2_region_set_version_id: EntityId
    side_2_source_file_id: EntityId
    side_2_region_id: EntityId
    side_2_geometry_recipe_version_id: EntityId
    layout: DocumentSideCompositionLayout
    outer_margin_px: int
    inter_side_gap_px: int
    composition_pipeline_id: str
    composition_pipeline_version: int
    jpeg_pipeline_id: str
    jpeg_pipeline_version: int
    output_contract_id: str
    output_contract_version: int
    created_at: datetime
    created_by: ActorRef
    correlation_id: EntityId

    def __post_init__(self) -> None:
        _require_ids(
            (
                self.id,
                self.composition_id,
                self.side_1_region_set_version_id,
                self.side_1_source_file_id,
                self.side_1_region_id,
                self.side_1_geometry_recipe_version_id,
                self.side_2_region_set_version_id,
                self.side_2_source_file_id,
                self.side_2_region_id,
                self.side_2_geometry_recipe_version_id,
                self.correlation_id,
            )
        )
        if not isinstance(self.layout, DocumentSideCompositionLayout):
            raise DocumentSideCompositionError(
                DocumentSideCompositionErrorCode.COMPOSITION_LAYOUT_INVALID
            )
        if type(self.outer_margin_px) is not int or not 0 <= self.outer_margin_px <= 256:
            raise DocumentSideCompositionError(
                DocumentSideCompositionErrorCode.COMPOSITION_MARGIN_INVALID
            )
        if type(self.inter_side_gap_px) is not int or not 0 <= self.inter_side_gap_px <= 256:
            raise DocumentSideCompositionError(
                DocumentSideCompositionErrorCode.COMPOSITION_GAP_INVALID
            )
        if (self.composition_pipeline_id, self.composition_pipeline_version) != (
            DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID,
            DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION,
        ):
            raise DocumentSideCompositionError(
                DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID
            )
        from document_intake.domain.prepared_jpeg import (
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
            PREPARED_JPEG_PIPELINE_ID,
            PREPARED_JPEG_PIPELINE_VERSION,
        )

        if (self.jpeg_pipeline_id, self.jpeg_pipeline_version) != (
            PREPARED_JPEG_PIPELINE_ID,
            PREPARED_JPEG_PIPELINE_VERSION,
        ) or (self.output_contract_id, self.output_contract_version) != (
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
        ):
            raise DocumentSideCompositionError(
                DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID
            )
        _require_utc(self.created_at)
        if not isinstance(self.created_by, ActorRef):
            raise DocumentSideCompositionError(
                DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID
            )

    def __repr__(self) -> str:
        return "DocumentSideCompositionVersion(<redacted>)"


@dataclass(frozen=True, slots=True)
class PreparedCompositionArtifact:
    id: EntityId
    composition_version_id: EntityId
    stored_artifact_id: EntityId
    pipeline_id: str
    pipeline_version: int
    output_contract_id: str
    output_contract_version: int
    media_type: PreparedMediaType
    color_space: ColorSpace
    width: int
    height: int
    byte_size: int
    sha256: Sha256Digest
    jpeg_quality: int
    resize_percent: int
    created_at: datetime
    created_by: ActorRef

    def __post_init__(self) -> None:
        _require_ids((self.id, self.composition_version_id, self.stored_artifact_id))
        valid = (
            _artifact_identity_valid(self)
            and _artifact_dimensions_valid(self)
            and _artifact_quality_valid(self)
        )
        if not valid:
            raise DocumentSideCompositionError(
                DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID
            )
        _require_utc(self.created_at)

    def __repr__(self) -> str:
        return "PreparedCompositionArtifact(<redacted>)"
