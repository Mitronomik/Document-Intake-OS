"""PR-008 upload batch and source-file import services."""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass
from pathlib import Path

from document_intake.application.dto.imports import (
    CreateUploadBatchCommand,
    FailedSourceFileResult,
    ImportedSourceFileResult,
    ImportSourceFilesCommand,
    ImportSourceFilesResult,
    SourceFileImportInput,
)
from document_intake.application.ports.media import MediaDecoderPort
from document_intake.application.ports.persistence import UnitOfWorkFactory
from document_intake.application.ports.storage import StoragePort
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.entities.imports import ImportWarning, SourceFile, UploadBatch
from document_intake.domain.enums import (
    ArtifactKind,
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    ImportWarningCode,
    SourceImportErrorCode,
    SourceMediaType,
    UploadBatchStatus,
)
from document_intake.domain.value_objects import EntityId
from document_intake.domain.value_objects.audit import AuditReasonCode, AuditValueSummary
from document_intake.domain.value_objects.imports import PerceptualHash, Sha256Digest, SourceBasename
from document_intake.image_pipeline.media_decoder import (
    MediaDecodeError,
    dhash64,
    dhash64_hamming_distance,
)
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode

_EXTENSION_MEDIA_TYPES = {
    ".jpg": SourceMediaType.JPEG,
    ".jpeg": SourceMediaType.JPEG,
    ".png": SourceMediaType.PNG,
    ".heic": SourceMediaType.HEIF,
    ".heif": SourceMediaType.HEIF,
}


@dataclass(frozen=True, slots=True)
class _ReadSnapshot:
    size: int
    mtime_ns: int
    inode: int | None


class _ImportItemFailure(Exception):
    def __init__(self, code: SourceImportErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def create_upload_batch(
    command: CreateUploadBatchCommand,
    *,
    unit_of_work_factory: UnitOfWorkFactory,
) -> UploadBatch:
    batch = UploadBatch(
        id=command.batch_id,
        number=command.number,
        created_at=command.created_at,
        created_by=command.actor,
        status=UploadBatchStatus.NEW,
        source_file_ids=(),
    )
    with unit_of_work_factory.unit_of_work() as uow:
        if uow.upload_batches.get(batch.id) is not None:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        if uow.upload_batches.get_by_number(batch.number) is not None:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        uow.upload_batches.add(batch)
        uow.commit()
    return batch


def _failed(item: SourceFileImportInput, code: SourceImportErrorCode) -> FailedSourceFileResult:
    return FailedSourceFileResult(source_file_id=item.source_file_id, error_code=code)


def _safe_stat(path: Path) -> _ReadSnapshot:
    try:
        result = path.stat()
    except OSError:
        raise _ImportItemFailure(SourceImportErrorCode.SOURCE_READ_FAILED) from None
    if not stat.S_ISREG(result.st_mode):
        raise _ImportItemFailure(SourceImportErrorCode.SOURCE_READ_FAILED)
    return _ReadSnapshot(
        size=result.st_size,
        mtime_ns=result.st_mtime_ns,
        inode=getattr(result, "st_ino", None),
    )


def _read_exactly_once(path: Path) -> bytes:
    before = _safe_stat(path)
    try:
        content = path.read_bytes()
    except OSError:
        raise _ImportItemFailure(SourceImportErrorCode.SOURCE_READ_FAILED) from None
    after = _safe_stat(path)
    if before != after or not content or len(content) != after.size:
        raise _ImportItemFailure(SourceImportErrorCode.SOURCE_READ_FAILED)
    return content


def _read_import_input(item: SourceFileImportInput) -> tuple[SourceBasename, SourceMediaType, bytes]:
    try:
        basename = SourceBasename(item.source_path.name)
    except Exception:
        raise _ImportItemFailure(SourceImportErrorCode.SOURCE_BASENAME_INVALID) from None
    expected_media_type = _EXTENSION_MEDIA_TYPES.get(item.source_path.suffix.lower())
    if expected_media_type is None:
        raise _ImportItemFailure(SourceImportErrorCode.UNSUPPORTED_EXTENSION)
    return basename, expected_media_type, _read_exactly_once(item.source_path)


def _exact_warnings(
    item: SourceFileImportInput,
    exact_matches: tuple[SourceFile, ...],
) -> tuple[ImportWarning, ...]:
    related_ids = sorted({source_file.id for source_file in exact_matches}, key=str)
    return tuple(
        ImportWarning(
            code=ImportWarningCode.EXACT_DUPLICATE,
            source_file_id=item.source_file_id,
            related_source_file_id=related_id,
            perceptual_distance=None,
            algorithm_id=None,
            algorithm_version=None,
        )
        for related_id in related_ids
    )


def _perceptual_warnings(
    item: SourceFileImportInput,
    perceptual_hash: PerceptualHash,
    candidates: tuple[SourceFile, ...],
    exact_related_ids: set[EntityId],
) -> tuple[ImportWarning, ...]:
    best_by_id: dict[EntityId, int] = {}
    for candidate in candidates:
        if candidate.id in exact_related_ids:
            continue
        distance = dhash64_hamming_distance(
            perceptual_hash.hex_value,
            candidate.perceptual_hash.hex_value,
        )
        if distance <= 8:
            current = best_by_id.get(candidate.id)
            if current is None or distance < current:
                best_by_id[candidate.id] = distance
    return tuple(
        ImportWarning(
            code=ImportWarningCode.PERCEPTUAL_SIMILARITY,
            source_file_id=item.source_file_id,
            related_source_file_id=related_id,
            perceptual_distance=distance,
            algorithm_id="DHASH64",
            algorithm_version=1,
        )
        for related_id, distance in sorted(best_by_id.items(), key=lambda entry: (entry[1], str(entry[0])))
    )


def _audit_event(command: ImportSourceFilesCommand, item: SourceFileImportInput) -> AuditEvent:
    return AuditEvent(
        event_id=item.audit_event_id,
        occurred_at=item.imported_at,
        actor=command.actor,
        action_code=AuditAction.ARTIFACT_REGISTERED,
        subject_type=AuditSubjectType.STORED_ARTIFACT,
        subject_id=item.artifact_id,
        field_key=None,
        before=AuditValueSummary(
            classification=AuditValueClassification.ABSENT,
            display_value=None,
            was_present=False,
        ),
        after=AuditValueSummary(
            classification=AuditValueClassification.NON_SENSITIVE,
            display_value="ORIGINAL",
            was_present=True,
        ),
        reason_code=AuditReasonCode("SOURCE_FILE_IMPORT"),
        correlation_id=command.batch_id,
    )


def import_source_files(
    command: ImportSourceFilesCommand,
    *,
    storage: StoragePort,
    media_decoder: MediaDecoderPort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> ImportSourceFilesResult:
    imported: list[ImportedSourceFileResult] = []
    failed: list[FailedSourceFileResult] = []
    try:
        with unit_of_work_factory.unit_of_work() as uow:
            batch = uow.upload_batches.get(command.batch_id)
    except Exception:
        return ImportSourceFilesResult(
            batch_id=command.batch_id,
            imported=(),
            failed=tuple(_failed(item, SourceImportErrorCode.PERSISTENCE_FAILED) for item in command.items),
        )
    if batch is None:
        return ImportSourceFilesResult(
            batch_id=command.batch_id,
            imported=(),
            failed=tuple(_failed(item, SourceImportErrorCode.BATCH_NOT_FOUND) for item in command.items),
        )

    for item in command.items:
        try:
            basename, expected_media_type, content = _read_import_input(item)
            try:
                decoded = media_decoder.decode_for_import(content=content)
            except MediaDecodeError as error:
                raise _ImportItemFailure(error.code) from None
            except Exception:
                raise _ImportItemFailure(SourceImportErrorCode.DECODE_FAILED) from None
            sha256 = Sha256Digest(hashlib.sha256(content).hexdigest())
            perceptual_hash = PerceptualHash(
                algorithm_id="DHASH64",
                algorithm_version=1,
                bit_width=64,
                hex_value=dhash64(
                    decoded.grayscale_pixels,
                    decoded.grayscale_width,
                    decoded.grayscale_height,
                ),
            )
            try:
                with unit_of_work_factory.unit_of_work() as lookup_uow:
                    exact_matches = tuple(
                        source_file
                        for source_file in lookup_uow.source_files.list_by_sha256(sha256)
                        if source_file.id != item.source_file_id
                        and source_file.original_artifact_id != item.artifact_id
                    )
                    perceptual_candidates = tuple(
                        source_file
                        for source_file in lookup_uow.source_files.list_compatible_perceptual_hashes(
                            "DHASH64",
                            1,
                            64,
                        )
                        if source_file.id != item.source_file_id
                        and source_file.original_artifact_id != item.artifact_id
                    )
            except Exception:
                raise _ImportItemFailure(SourceImportErrorCode.PERSISTENCE_FAILED) from None

            exact = _exact_warnings(item, exact_matches)
            exact_related_ids = {warning.related_source_file_id for warning in exact}
            warnings = [*exact]
            warnings.extend(
                _perceptual_warnings(
                    item,
                    perceptual_hash,
                    perceptual_candidates,
                    exact_related_ids,
                )
            )
            if decoded.media_type is not expected_media_type:
                warnings.append(
                    ImportWarning(
                        code=ImportWarningCode.EXTENSION_CONTENT_MISMATCH,
                        source_file_id=item.source_file_id,
                        related_source_file_id=None,
                        perceptual_distance=None,
                        algorithm_id=None,
                        algorithm_version=None,
                    )
                )
            source_file = SourceFile(
                id=item.source_file_id,
                batch_id=command.batch_id,
                original_artifact_id=item.artifact_id,
                original_basename=basename,
                detected_media_type=decoded.media_type,
                byte_size=len(content),
                sha256=sha256,
                perceptual_hash=perceptual_hash,
                width=decoded.width,
                height=decoded.height,
                exif_orientation=decoded.exif_orientation,
                imported_at=item.imported_at,
                imported_by=command.actor,
            )
            try:
                stored_artifact = storage.publish_bytes(
                    artifact_id=item.artifact_id,
                    artifact_kind=ArtifactKind.ORIGINAL,
                    plaintext=content,
                    created_at=item.imported_at,
                )
            except Exception:
                raise _ImportItemFailure(SourceImportErrorCode.STORAGE_PUBLICATION_FAILED) from None
            if stored_artifact.artifact_id != item.artifact_id:
                raise _ImportItemFailure(SourceImportErrorCode.STORAGE_PUBLICATION_FAILED)
            try:
                with unit_of_work_factory.unit_of_work() as write_uow:
                    current_batch = write_uow.upload_batches.get(command.batch_id)
                    if current_batch is None or current_batch.status is not UploadBatchStatus.NEW:
                        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
                    if write_uow.source_files.get(item.source_file_id) is not None:
                        raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
                    if write_uow.stored_artifacts.get(item.artifact_id) is not None:
                        raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
                    write_uow.stored_artifacts.add(stored_artifact)
                    write_uow.source_files.add(source_file)
                    write_uow.upload_batches.update(
                        current_batch.append_source_file_id(item.source_file_id)
                    )
                    write_uow.audit_events.add(_audit_event(command, item))
                    write_uow.commit()
            except Exception:
                raise _ImportItemFailure(SourceImportErrorCode.PERSISTENCE_FAILED) from None
        except _ImportItemFailure as failure:
            failed.append(_failed(item, failure.code))
            continue
        imported.append(ImportedSourceFileResult(source_file=source_file, warnings=tuple(warnings)))
    return ImportSourceFilesResult(
        batch_id=command.batch_id,
        imported=tuple(imported),
        failed=tuple(failed),
    )
