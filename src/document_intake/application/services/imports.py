"""PR-008 upload batch and source-file import services."""
from __future__ import annotations
import hashlib
from document_intake.application.dto.imports import *
from document_intake.application.ports.media import MediaDecoderPort
from document_intake.application.ports.persistence import UnitOfWorkFactory
from document_intake.application.ports.storage import StoragePort
from document_intake.domain import *
from document_intake.domain.enums import *
from document_intake.image_pipeline.media_decoder import MediaDecodeError, dhash64, dhash64_hamming_distance
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
_EXT = {".jpg": SourceMediaType.JPEG, ".jpeg": SourceMediaType.JPEG, ".png": SourceMediaType.PNG, ".heic": SourceMediaType.HEIF, ".heif": SourceMediaType.HEIF}

def create_upload_batch(command: CreateUploadBatchCommand, *, unit_of_work_factory: UnitOfWorkFactory) -> UploadBatch:
    batch = UploadBatch(command.batch_id, command.number, command.created_at, command.actor, UploadBatchStatus.NEW, ())
    with unit_of_work_factory.unit_of_work() as uow:
        if uow.upload_batches.get(batch.batch_id) is not None or uow.upload_batches.get_by_number(batch.number) is not None:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        uow.upload_batches.add(batch); uow.commit()
    return batch

def _failure(item: SourceFileImportInput, code: SourceImportErrorCode) -> FailedSourceFileResult:
    return FailedSourceFileResult(item.source_file_id, code)

def import_source_files(command: ImportSourceFilesCommand, *, storage: StoragePort, media_decoder: MediaDecoderPort, unit_of_work_factory: UnitOfWorkFactory) -> ImportSourceFilesResult:
    imported: list[ImportedSourceFileResult] = []; failed: list[FailedSourceFileResult] = []
    try:
        with unit_of_work_factory.unit_of_work() as uow: batch = uow.upload_batches.get(command.batch_id)
    except Exception: batch = None
    if batch is None:
        return ImportSourceFilesResult(command.batch_id, (), tuple(_failure(i, SourceImportErrorCode.BATCH_NOT_FOUND) for i in command.items))
    for item in command.items:
        try:
            basename = SourceBasename(item.source_path.name); expected = _EXT.get(item.source_path.suffix.lower())
            if expected is None: failed.append(_failure(item, SourceImportErrorCode.UNSUPPORTED_EXTENSION)); continue
            if not item.source_path.is_file(): failed.append(_failure(item, SourceImportErrorCode.SOURCE_READ_FAILED)); continue
            content = item.source_path.read_bytes()
            if not content: failed.append(_failure(item, SourceImportErrorCode.SOURCE_READ_FAILED)); continue
        except Exception:
            failed.append(_failure(item, SourceImportErrorCode.SOURCE_BASENAME_INVALID)); continue
        try:
            decoded = media_decoder.decode_for_import(content=content)
        except MediaDecodeError as exc:
            failed.append(_failure(item, exc.code)); continue
        except Exception:
            failed.append(_failure(item, SourceImportErrorCode.DECODE_FAILED)); continue
        sha = Sha256Digest(hashlib.sha256(content).hexdigest()); ph = PerceptualHash("DHASH64", 1, 64, dhash64(decoded.grayscale_pixels, decoded.grayscale_width, decoded.grayscale_height))
        try:
            with unit_of_work_factory.unit_of_work() as lookup:
                exact = tuple(s for s in lookup.source_files.list_by_sha256(sha) if s.source_file_id != item.source_file_id and s.original_artifact_id != item.artifact_id)
                candidates = tuple(s for s in lookup.source_files.list_compatible_perceptual_hashes("DHASH64", 1, 64) if s.source_file_id != item.source_file_id and s.original_artifact_id != item.artifact_id)
        except Exception:
            failed.append(_failure(item, SourceImportErrorCode.PERSISTENCE_FAILED)); continue
        exact_ids = {s.source_file_id for s in exact}; warnings: list[ImportWarning] = [ImportWarning(ImportWarningCode.EXACT_DUPLICATE, item.source_file_id, s.source_file_id) for s in sorted(exact, key=lambda s: str(s.source_file_id))]
        perceptual = []
        for c in candidates:
            if c.source_file_id in exact_ids: continue
            d = dhash64_hamming_distance(ph.hex_value, c.perceptual_hash.hex_value)
            if d <= 8: perceptual.append((d, c.source_file_id))
        warnings.extend(ImportWarning(ImportWarningCode.PERCEPTUAL_SIMILARITY, item.source_file_id, rid, d) for d, rid in sorted(perceptual, key=lambda x: (x[0], str(x[1]))))
        if decoded.media_type is not expected: warnings.append(ImportWarning(ImportWarningCode.EXTENSION_CONTENT_MISMATCH, item.source_file_id))
        sf = SourceFile(item.source_file_id, command.batch_id, item.artifact_id, basename, decoded.media_type, len(content), sha, ph, decoded.width, decoded.height, decoded.exif_orientation, item.imported_at, command.actor)
        try:
            artifact = storage.publish_bytes(artifact_id=item.artifact_id, artifact_kind=ArtifactKind.ORIGINAL, plaintext=content, created_at=item.imported_at)
            if artifact.artifact_id != item.artifact_id: failed.append(_failure(item, SourceImportErrorCode.STORAGE_PUBLICATION_FAILED)); continue
        except Exception:
            failed.append(_failure(item, SourceImportErrorCode.STORAGE_PUBLICATION_FAILED)); continue
        try:
            with unit_of_work_factory.unit_of_work() as uow:
                current = uow.upload_batches.get(command.batch_id)
                if current is None or uow.source_files.get(item.source_file_id) is not None or uow.stored_artifacts.get(item.artifact_id) is not None: raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
                uow.stored_artifacts.add(artifact); uow.source_files.add(sf); uow.upload_batches.update(current.append_source_file_id(item.source_file_id))
                uow.audit_events.add(AuditEvent(item.audit_event_id, item.imported_at, command.actor, AuditAction.ARTIFACT_REGISTERED, AuditSubjectType.STORED_ARTIFACT, item.artifact_id, None, AuditValueSummary(AuditValueClassification.ABSENT, None, False), AuditValueSummary(AuditValueClassification.NON_SENSITIVE, "ORIGINAL", True), AuditReasonCode("SOURCE_FILE_IMPORT"), command.batch_id)); uow.commit()
        except Exception:
            failed.append(_failure(item, SourceImportErrorCode.PERSISTENCE_FAILED)); continue
        imported.append(ImportedSourceFileResult(sf, tuple(warnings)))
    return ImportSourceFilesResult(command.batch_id, tuple(imported), tuple(failed))
