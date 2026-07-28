"""Immutable PR-011 prepared JPEG domain contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from document_intake.domain.enums import ColorSpace, PreparedMediaType
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId, Sha256Digest

MAX_PREPARED_JPEG_BYTES = 1_992_294
PREPARED_JPEG_PIPELINE_ID = "PILLOW_PREPARED_JPEG"
PREPARED_JPEG_PIPELINE_VERSION = 1
PREPARED_JPEG_OUTPUT_CONTRACT_ID = "PREPARED_JPEG_SRGB_V1"
PREPARED_JPEG_OUTPUT_CONTRACT_VERSION = 1
JPEG_QUALITY_SEQUENCE = (95, 90, 85, 80, 75, 70, 65, 60)
JPEG_RESIZE_PERCENT_SEQUENCE = (100, 90, 80, 70, 60, 50)


@dataclass(frozen=True, slots=True)
class PreparedJpegPipelineVersion:
    pipeline_id: str = PREPARED_JPEG_PIPELINE_ID
    version: int = PREPARED_JPEG_PIPELINE_VERSION

    def __post_init__(self) -> None:
        if (self.pipeline_id, self.version) != (
            PREPARED_JPEG_PIPELINE_ID,
            PREPARED_JPEG_PIPELINE_VERSION,
        ):
            raise InvalidValueError("prepared_jpeg.pipeline: invalid_identity")


class PreparedJpegErrorCode(StrEnum):
    GEOMETRY_RECIPE_NOT_FOUND = "GEOMETRY_RECIPE_NOT_FOUND"
    SOURCE_FILE_NOT_FOUND = "SOURCE_FILE_NOT_FOUND"
    ORIGINAL_ARTIFACT_NOT_FOUND = "ORIGINAL_ARTIFACT_NOT_FOUND"
    ORIGINAL_BYTES_INVALID = "ORIGINAL_BYTES_INVALID"
    SOURCE_DIMENSIONS_MISMATCH = "SOURCE_DIMENSIONS_MISMATCH"
    GEOMETRY_RENDER_FAILED = "GEOMETRY_RENDER_FAILED"
    JPEG_ENCODING_FAILED = "JPEG_ENCODING_FAILED"
    SIZE_LIMIT_UNREACHABLE = "SIZE_LIMIT_UNREACHABLE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    PREPARATION_ALREADY_EXISTS = "PREPARATION_ALREADY_EXISTS"
    STORAGE_PUBLICATION_FAILED = "STORAGE_PUBLICATION_FAILED"
    PERSISTENCE_CONFLICT = "PERSISTENCE_CONFLICT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    PERSISTED_DATA_INVALID = "PERSISTED_DATA_INVALID"


class PreparedJpegError(Exception):
    def __init__(self, code: PreparedJpegErrorCode) -> None:
        self.code = code
        super().__init__(code.value)

    def __repr__(self) -> str:
        return f"PreparedJpegError({self.code.value})"


@dataclass(frozen=True, slots=True)
class PreparedImageArtifact:
    id: EntityId
    source_file_id: EntityId
    geometry_recipe_version_id: EntityId
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
        if not all(
            isinstance(v, EntityId)
            for v in (
                self.id,
                self.source_file_id,
                self.geometry_recipe_version_id,
                self.stored_artifact_id,
            )
        ):
            raise InvalidValueError("prepared_image_artifact.id: invalid_type")
        if (self.pipeline_id, self.pipeline_version) != (PREPARED_JPEG_PIPELINE_ID, 1):
            raise InvalidValueError("prepared_image_artifact.pipeline: invalid_identity")
        if (self.output_contract_id, self.output_contract_version) != (
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            1,
        ):
            raise InvalidValueError("prepared_image_artifact.output_contract: invalid_identity")
        if self.media_type is not PreparedMediaType.JPEG or self.color_space is not ColorSpace.SRGB:
            raise InvalidValueError("prepared_image_artifact.media: invalid_identity")
        if (
            type(self.width) is not int
            or self.width < 1
            or type(self.height) is not int
            or self.height < 1
        ):
            raise InvalidValueError("prepared_image_artifact.dimensions: invalid_value")
        if type(self.byte_size) is not int or not 1 <= self.byte_size <= MAX_PREPARED_JPEG_BYTES:
            raise InvalidValueError("prepared_image_artifact.byte_size: invalid_value")
        if not isinstance(self.sha256, Sha256Digest):
            raise InvalidValueError("prepared_image_artifact.sha256: invalid_type")
        if (
            self.jpeg_quality not in JPEG_QUALITY_SEQUENCE
            or self.resize_percent not in JPEG_RESIZE_PERCENT_SEQUENCE
        ):
            raise InvalidValueError("prepared_image_artifact.encoder_setting: invalid_value")
        if (
            self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
            or self.created_at.utcoffset() != UTC.utcoffset(self.created_at)
        ):
            raise InvalidValueError("prepared_image_artifact.created_at: utc_required")
        if not isinstance(self.created_by, ActorRef):
            raise InvalidValueError("prepared_image_artifact.created_by: invalid_type")
