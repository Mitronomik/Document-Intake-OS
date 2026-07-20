"""Application DTOs for PR-008 imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from document_intake.domain.entities.imports import ImportWarning, SourceFile
from document_intake.domain.enums import SourceImportErrorCode
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import BatchNumber


@dataclass(frozen=True, slots=True)
class CreateUploadBatchCommand:
    batch_id: EntityId
    number: BatchNumber
    created_at: datetime
    actor: ActorRef

    def __post_init__(self) -> None:
        if not isinstance(self.batch_id, EntityId):
            raise InvalidValueError("create_upload_batch.batch_id: invalid_type")
        if not isinstance(self.number, BatchNumber):
            raise InvalidValueError("create_upload_batch.number: invalid_type")
        if not isinstance(self.created_at, datetime):
            raise InvalidValueError("create_upload_batch.created_at: invalid_type")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidValueError("create_upload_batch.created_at: timezone_aware_required")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        if not isinstance(self.actor, ActorRef):
            raise InvalidValueError("create_upload_batch.actor: invalid_type")

    def __repr__(self) -> str:
        return f"CreateUploadBatchCommand(batch_id={self.batch_id}, number={self.number!r})"


@dataclass(frozen=True, slots=True)
class SourceFileImportInput:
    source_file_id: EntityId
    artifact_id: EntityId
    audit_event_id: EntityId
    source_path: Path
    imported_at: datetime

    def __post_init__(self) -> None:
        ids = (self.source_file_id, self.artifact_id, self.audit_event_id)
        if any(not isinstance(value, EntityId) for value in ids):
            raise InvalidValueError("source_file_import_input.id: invalid_type")
        if len(set(ids)) != 3:
            raise InvalidValueError("source_file_import_input.id: not_distinct")
        if not isinstance(self.source_path, Path):
            raise InvalidValueError("source_file_import_input.source_path: invalid_type")
        if not isinstance(self.imported_at, datetime):
            raise InvalidValueError("source_file_import_input.imported_at: invalid_type")
        if self.imported_at.tzinfo is None or self.imported_at.utcoffset() is None:
            raise InvalidValueError("source_file_import_input.imported_at: timezone_aware_required")
        object.__setattr__(self, "imported_at", self.imported_at.astimezone(UTC))

    def __repr__(self) -> str:
        return (
            f"SourceFileImportInput(source_file_id={self.source_file_id}, "
            f"artifact_id={self.artifact_id}, audit_event_id={self.audit_event_id}, "
            "source_path=<redacted>)"
        )


@dataclass(frozen=True, slots=True)
class ImportSourceFilesCommand:
    batch_id: EntityId
    actor: ActorRef
    items: tuple[SourceFileImportInput, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.batch_id, EntityId):
            raise InvalidValueError("import_source_files.batch_id: invalid_type")
        if not isinstance(self.actor, ActorRef):
            raise InvalidValueError("import_source_files.actor: invalid_type")
        if type(self.items) is not tuple:
            raise InvalidValueError("import_source_files.items: invalid_type")
        if not self.items:
            raise InvalidValueError("import_source_files.items: empty")
        if any(not isinstance(item, SourceFileImportInput) for item in self.items):
            raise InvalidValueError("import_source_files.items: invalid_member")
        for attr in ("source_file_id", "artifact_id", "audit_event_id"):
            values = tuple(getattr(item, attr) for item in self.items)
            if len(values) != len(set(values)):
                raise InvalidValueError(f"import_source_files.{attr}: duplicate")

    def __repr__(self) -> str:
        return f"ImportSourceFilesCommand(batch_id={self.batch_id}, actor={self.actor}, items=<redacted>)"


@dataclass(frozen=True, slots=True)
class ImportedSourceFileResult:
    source_file: SourceFile
    warnings: tuple[ImportWarning, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_file, SourceFile):
            raise InvalidValueError("imported_source_file_result.source_file: invalid_type")
        if type(self.warnings) is not tuple or any(
            not isinstance(warning, ImportWarning) for warning in self.warnings
        ):
            raise InvalidValueError("imported_source_file_result.warnings: invalid_type")


@dataclass(frozen=True, slots=True)
class FailedSourceFileResult:
    source_file_id: EntityId
    error_code: SourceImportErrorCode

    def __post_init__(self) -> None:
        if not isinstance(self.source_file_id, EntityId):
            raise InvalidValueError("failed_source_file_result.source_file_id: invalid_type")
        if not isinstance(self.error_code, SourceImportErrorCode):
            raise InvalidValueError("failed_source_file_result.error_code: invalid_type")


@dataclass(frozen=True, slots=True)
class ImportSourceFilesResult:
    batch_id: EntityId
    imported: tuple[ImportedSourceFileResult, ...]
    failed: tuple[FailedSourceFileResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.batch_id, EntityId):
            raise InvalidValueError("import_source_files_result.batch_id: invalid_type")
        if type(self.imported) is not tuple or any(
            not isinstance(item, ImportedSourceFileResult) for item in self.imported
        ):
            raise InvalidValueError("import_source_files_result.imported: invalid_type")
        if type(self.failed) is not tuple or any(
            not isinstance(item, FailedSourceFileResult) for item in self.failed
        ):
            raise InvalidValueError("import_source_files_result.failed: invalid_type")
        imported_ids = {item.source_file.id for item in self.imported}
        failed_ids = {item.source_file_id for item in self.failed}
        if imported_ids & failed_ids:
            raise InvalidValueError("import_source_files_result: duplicate_outcome")
