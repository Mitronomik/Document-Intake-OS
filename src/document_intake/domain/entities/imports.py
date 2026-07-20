"""PR-008 source import entities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from document_intake.domain.enums import ImportWarningCode, SourceMediaType, UploadBatchStatus
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import BatchNumber, PerceptualHash, Sha256Digest, SourceBasename


@dataclass(frozen=True, slots=True)
class UploadBatch:
    batch_id: EntityId
    number: BatchNumber
    created_at: datetime
    created_by: ActorRef
    status: UploadBatchStatus
    source_file_ids: tuple[EntityId, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.batch_id, EntityId) or not isinstance(self.number, BatchNumber):
            raise InvalidValueError("upload_batch: invalid_identity")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidValueError("upload_batch.created_at: timezone_aware_required")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        if not isinstance(self.created_by, ActorRef) or not isinstance(self.status, UploadBatchStatus):
            raise InvalidValueError("upload_batch: invalid_type")
        if self.status is not UploadBatchStatus.NEW:
            raise InvalidValueError("upload_batch.status: unauthorized_for_pr008")
        if not isinstance(self.source_file_ids, tuple) or any(not isinstance(i, EntityId) for i in self.source_file_ids):
            raise InvalidValueError("upload_batch.source_file_ids: invalid_type")
        if len(set(self.source_file_ids)) != len(self.source_file_ids):
            raise InvalidValueError("upload_batch.source_file_ids: duplicate")

    def append_source_file_id(self, source_file_id: EntityId) -> UploadBatch:
        return replace(self, source_file_ids=(*self.source_file_ids, source_file_id))


@dataclass(frozen=True, slots=True)
class SourceFile:
    source_file_id: EntityId
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
        for value in (self.source_file_id, self.batch_id, self.original_artifact_id):
            if not isinstance(value, EntityId):
                raise InvalidValueError("source_file.id: invalid_type")
        if len({self.source_file_id, self.batch_id, self.original_artifact_id}) != 3:
            raise InvalidValueError("source_file.id: not_distinct")
        if not isinstance(self.original_basename, SourceBasename) or not isinstance(self.detected_media_type, SourceMediaType):
            raise InvalidValueError("source_file: invalid_type")
        if not isinstance(self.byte_size, int) or self.byte_size <= 0:
            raise InvalidValueError("source_file.byte_size: invalid_value")
        if not isinstance(self.sha256, Sha256Digest) or not isinstance(self.perceptual_hash, PerceptualHash):
            raise InvalidValueError("source_file.hash: invalid_type")
        if self.width <= 0 or self.height <= 0:
            raise InvalidValueError("source_file.dimensions: invalid_value")
        if self.exif_orientation is not None and self.exif_orientation not in range(1, 9):
            raise InvalidValueError("source_file.exif_orientation: invalid_value")
        if not isinstance(self.imported_by, ActorRef) or self.imported_at.tzinfo is None or self.imported_at.utcoffset() is None:
            raise InvalidValueError("source_file.import: invalid_type")
        object.__setattr__(self, "imported_at", self.imported_at.astimezone(UTC))

    def __repr__(self) -> str:
        return f"SourceFile(source_file_id={self.source_file_id}, batch_id={self.batch_id}, original_artifact_id={self.original_artifact_id}, original_basename=<redacted>)"


@dataclass(frozen=True, slots=True)
class ImportWarning:
    code: ImportWarningCode
    source_file_id: EntityId
    related_source_file_id: EntityId | None = None
    hamming_distance: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, ImportWarningCode) or not isinstance(self.source_file_id, EntityId):
            raise InvalidValueError("import_warning: invalid_type")
        if self.related_source_file_id is not None and not isinstance(self.related_source_file_id, EntityId):
            raise InvalidValueError("import_warning.related_source_file_id: invalid_type")
        if self.hamming_distance is not None and (not isinstance(self.hamming_distance, int) or self.hamming_distance < 0):
            raise InvalidValueError("import_warning.hamming_distance: invalid_value")
