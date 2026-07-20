"""Application DTOs for PR-008 imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from document_intake.domain import ActorRef, EntityId, ImportWarning, SourceFile
from document_intake.domain.enums import SourceImportErrorCode
from document_intake.domain.value_objects.imports import BatchNumber


@dataclass(frozen=True, slots=True)
class CreateUploadBatchCommand:
    batch_id: EntityId
    number: BatchNumber
    created_at: datetime
    actor: ActorRef


@dataclass(frozen=True, slots=True)
class SourceFileImportInput:
    source_file_id: EntityId
    artifact_id: EntityId
    audit_event_id: EntityId
    source_path: Path
    imported_at: datetime

    def __repr__(self) -> str:
        return f"SourceFileImportInput(source_file_id={self.source_file_id}, artifact_id={self.artifact_id}, audit_event_id={self.audit_event_id}, source_path=<redacted>)"


@dataclass(frozen=True, slots=True)
class ImportSourceFilesCommand:
    batch_id: EntityId
    actor: ActorRef
    items: tuple[SourceFileImportInput, ...]

    def __post_init__(self) -> None:
        for attr in ("source_file_id", "artifact_id", "audit_event_id"):
            values = [getattr(item, attr) for item in self.items]
            if len(values) != len(set(values)):
                raise ValueError(f"ERR_IMPORT_DUPLICATE_{attr.upper()}")

    def __repr__(self) -> str:
        return f"ImportSourceFilesCommand(batch_id={self.batch_id}, actor={self.actor}, items=<redacted>)"


@dataclass(frozen=True, slots=True)
class ImportedSourceFileResult:
    source_file: SourceFile
    warnings: tuple[ImportWarning, ...]


@dataclass(frozen=True, slots=True)
class FailedSourceFileResult:
    source_file_id: EntityId
    error_code: SourceImportErrorCode


@dataclass(frozen=True, slots=True)
class ImportSourceFilesResult:
    batch_id: EntityId
    imported: tuple[ImportedSourceFileResult, ...]
    failed: tuple[FailedSourceFileResult, ...]
