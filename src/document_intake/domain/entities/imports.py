"""PR-008 source import entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from document_intake.domain.enums import ImportWarningCode, SourceMediaType, UploadBatchStatus
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import (
    BatchNumber,
    PerceptualHash,
    Sha256Digest,
    SourceBasename,
)


@dataclass(frozen=True, slots=True)
class UploadBatch:
    id: EntityId
    number: BatchNumber
    created_at: datetime
    created_by: ActorRef
    status: UploadBatchStatus
    source_file_ids: tuple[EntityId, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, EntityId):
            raise InvalidValueError("upload_batch.id: invalid_type")
        if not isinstance(self.number, BatchNumber):
            raise InvalidValueError("upload_batch.number: invalid_type")
        if not isinstance(self.created_at, datetime):
            raise InvalidValueError("upload_batch.created_at: invalid_type")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidValueError("upload_batch.created_at: timezone_aware_required")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        if not isinstance(self.created_by, ActorRef):
            raise InvalidValueError("upload_batch.created_by: invalid_type")
        if self.status is not UploadBatchStatus.NEW:
            raise InvalidValueError("upload_batch.status: unauthorized_for_pr008")
        if type(self.source_file_ids) is not tuple:
            raise InvalidValueError("upload_batch.source_file_ids: invalid_type")
        if any(not isinstance(source_id, EntityId) for source_id in self.source_file_ids):
            raise InvalidValueError("upload_batch.source_file_ids: invalid_member")
        if len(set(self.source_file_ids)) != len(self.source_file_ids):
            raise InvalidValueError("upload_batch.source_file_ids: duplicate")

    def append_source_file_id(self, source_file_id: EntityId) -> UploadBatch:
        if not isinstance(source_file_id, EntityId):
            raise InvalidValueError("upload_batch.append_source_file_id: invalid_type")
        if source_file_id in self.source_file_ids:
            raise InvalidValueError("upload_batch.append_source_file_id: duplicate")
        return replace(self, source_file_ids=(*self.source_file_ids, source_file_id))

    def __repr__(self) -> str:
        return (
            f"UploadBatch(id={self.id}, number={self.number!r}, "
            f"status={self.status.value!r}, source_count={len(self.source_file_ids)})"
        )


@dataclass(frozen=True, slots=True)
class SourceFile:
    id: EntityId
    batch_id: EntityId
    original_artifact_id: EntityId
    original_basename: SourceBasename
    detected_media_type: SourceMediaType
    byte_size: int
    sha256: Sha256Digest
    perceptual_hash: PerceptualHash
    width: int
    height: int
    exif_orientation: int | None
    imported_at: datetime
    imported_by: ActorRef

    def __post_init__(self) -> None:
        if not isinstance(self.id, EntityId):
            raise InvalidValueError("source_file.id: invalid_type")
        if not isinstance(self.batch_id, EntityId):
            raise InvalidValueError("source_file.batch_id: invalid_type")
        if not isinstance(self.original_artifact_id, EntityId):
            raise InvalidValueError("source_file.original_artifact_id: invalid_type")
        if not isinstance(self.original_basename, SourceBasename):
            raise InvalidValueError("source_file.original_basename: invalid_type")
        if not isinstance(self.detected_media_type, SourceMediaType):
            raise InvalidValueError("source_file.detected_media_type: invalid_type")
        if type(self.byte_size) is not int or self.byte_size <= 0:
            raise InvalidValueError("source_file.byte_size: invalid_value")
        if not isinstance(self.sha256, Sha256Digest):
            raise InvalidValueError("source_file.sha256: invalid_type")
        if not isinstance(self.perceptual_hash, PerceptualHash):
            raise InvalidValueError("source_file.perceptual_hash: invalid_type")
        if type(self.width) is not int or self.width <= 0:
            raise InvalidValueError("source_file.width: invalid_value")
        if type(self.height) is not int or self.height <= 0:
            raise InvalidValueError("source_file.height: invalid_value")
        if self.exif_orientation is not None and (
            type(self.exif_orientation) is not int or self.exif_orientation not in range(1, 9)
        ):
            raise InvalidValueError("source_file.exif_orientation: invalid_value")
        if not isinstance(self.imported_at, datetime):
            raise InvalidValueError("source_file.imported_at: invalid_type")
        if self.imported_at.tzinfo is None or self.imported_at.utcoffset() is None:
            raise InvalidValueError("source_file.imported_at: timezone_aware_required")
        object.__setattr__(self, "imported_at", self.imported_at.astimezone(UTC))
        if not isinstance(self.imported_by, ActorRef):
            raise InvalidValueError("source_file.imported_by: invalid_type")

    def __repr__(self) -> str:
        return (
            f"SourceFile(id={self.id}, batch_id={self.batch_id}, "
            f"original_artifact_id={self.original_artifact_id}, "
            f"detected_media_type={self.detected_media_type.value!r}, "
            f"byte_size={self.byte_size}, basename=<redacted>, sha256=<redacted>, "
            "perceptual_hash=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class ImportWarning:
    code: ImportWarningCode
    source_file_id: EntityId
    related_source_file_id: EntityId | None
    perceptual_distance: int | None
    algorithm_id: str | None
    algorithm_version: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.code, ImportWarningCode):
            raise InvalidValueError("import_warning.code: invalid_type")
        if not isinstance(self.source_file_id, EntityId):
            raise InvalidValueError("import_warning.source_file_id: invalid_type")
        if self.related_source_file_id is not None:
            if not isinstance(self.related_source_file_id, EntityId):
                raise InvalidValueError("import_warning.related_source_file_id: invalid_type")
            if self.related_source_file_id == self.source_file_id:
                raise InvalidValueError("import_warning.related_source_file_id: self_reference")
        if self.code is ImportWarningCode.EXACT_DUPLICATE:
            if self.related_source_file_id is None:
                raise InvalidValueError("import_warning.exact_duplicate: related_required")
            if self.perceptual_distance is not None or self.algorithm_id is not None or self.algorithm_version is not None:
                raise InvalidValueError("import_warning.exact_duplicate: invalid_fields")
        elif self.code is ImportWarningCode.PERCEPTUAL_SIMILARITY:
            if self.related_source_file_id is None:
                raise InvalidValueError("import_warning.perceptual: related_required")
            if type(self.perceptual_distance) is not int or not 0 <= self.perceptual_distance <= 8:
                raise InvalidValueError("import_warning.perceptual: invalid_distance")
            if self.algorithm_id != "DHASH64" or self.algorithm_version != 1:
                raise InvalidValueError("import_warning.perceptual: invalid_algorithm")
        elif self.code is ImportWarningCode.EXTENSION_CONTENT_MISMATCH:
            if (
                self.related_source_file_id is not None
                or self.perceptual_distance is not None
                or self.algorithm_id is not None
                or self.algorithm_version is not None
            ):
                raise InvalidValueError("import_warning.extension_mismatch: invalid_fields")

    def __repr__(self) -> str:
        return (
            f"ImportWarning(code={self.code.value!r}, source_file_id={self.source_file_id}, "
            f"related_present={self.related_source_file_id is not None}, "
            f"perceptual_distance={self.perceptual_distance!r}, "
            f"algorithm_id={self.algorithm_id!r}, algorithm_version={self.algorithm_version!r})"
        )
