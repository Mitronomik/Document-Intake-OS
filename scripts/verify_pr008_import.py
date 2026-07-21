"""Sanitized production-component verifier for PR-008."""

from __future__ import annotations

import hashlib
import importlib
import io
import platform
import re
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Self, cast
from uuid import UUID

from document_intake.application.dto.imports import (
    CreateUploadBatchCommand,
    ImportedSourceFileResult,
    ImportSourceFilesCommand,
    SourceFileImportInput,
)
from document_intake.application.ports.persistence import UnitOfWork, UnitOfWorkFactory
from document_intake.application.ports.storage import StorageKey
from document_intake.application.services.imports import create_upload_batch, import_source_files
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.entities.imports import SourceFile
from document_intake.domain.enums import (
    ActorKind,
    ArtifactKind,
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    ImportWarningCode,
    SourceImportErrorCode,
    SourceMediaType,
)
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import (
    BatchNumber,
    PerceptualHash,
    Sha256Digest,
    SourceBasename,
)
from document_intake.image_pipeline.media_decoder import (
    PillowMediaDecoder,
    dhash64_hamming_distance,
)
from document_intake.persistence import CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.migrations.v0001_initial import MIGRATION as V0001
from document_intake.persistence.migrations.v0002_stored_artifacts import MIGRATION as V0002
from document_intake.persistence.migrations.v0003_audit_events import MIGRATION as V0003
from document_intake.persistence.migrations.v0004_source_file_import import MIGRATION as V0004
from document_intake.persistence.migrations.v0005_image_quality import MIGRATION as V0005
from document_intake.storage.filesystem import ImmutableFilesystemStorage

_EXPECTED_MIGRATION_CHECKSUMS = (
    "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500",
    "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d",
    "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1",
    "a826d5bc07ba73e6d54fd25e9df8afb42028261040b7981bdd157caf26b1f7c6",
    "74f6376fbfd42ed4b9748cadd936daba3c26755a04ddc7cedee76ed2143d95f2",
)
_FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "synthetic" / "pr008_color_grid.heic"
_NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
_DATABASE_KEY = b"D" * 32
_STORAGE_KEY = b"S" * 32
_CHECKS = (
    "migration_v0004",
    "encrypted_storage",
    "byte_identity",
    "media_jpeg",
    "media_png",
    "media_heif",
    "extension_casefold",
    "extension_mismatch_warning",
    "unsupported_extension",
    "exact_duplicate",
    "perceptual_duplicate",
    "no_self_match",
    "warning_order",
    "partial_success",
    "audit_atomicity",
    "orphan_reconciliation",
    "privacy",
)
_INCONCLUSIVE_CODES = (
    "WINDOWS_SQLCIPHER_UNAVAILABLE",
    "HEIF_DECODER_UNAVAILABLE",
    "UNSUPPORTED_PLATFORM",
)
_GENERIC_FORBIDDEN_OUTPUT = (
    "/private/",
    "/tmp/",
    "\\",
    ".db",
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".heif",
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "Traceback",
    "Exception",
    "sha256=",
    "dhash=",
    "key=",
)
_LOWER_SHA256 = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
_SQLITE_PROBE = "SELECT name FROM sqlite_master"


@dataclass(frozen=True, slots=True)
class _VerificationRun:
    statuses: dict[str, bool]
    forbidden_values: tuple[str, ...]
    unexpected_failure: bool


class _DatabaseKeyProvider:
    def get_database_key(self) -> bytes:
        return _DATABASE_KEY


class _StorageKeyProvider:
    def get_current_key(self) -> StorageKey:
        return StorageKey(1, _STORAGE_KEY)

    def get_key(self, version: int) -> StorageKey:
        return StorageKey(version, _STORAGE_KEY)


class _FailingAuditRepo:
    def add(self, event: AuditEvent) -> None:
        del event
        raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)


class _FailingAuditUow:
    def __init__(self, inner: UnitOfWork) -> None:
        self._inner = inner
        self.audit_events = _FailingAuditRepo()

    def __enter__(self) -> Self:
        self._inner.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return self._inner.__exit__(exc_type, exc, traceback)

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)

    @property
    def upload_batches(self):  # type: ignore[no-untyped-def]
        return self._inner.upload_batches

    @property
    def source_files(self):  # type: ignore[no-untyped-def]
        return self._inner.source_files

    @property
    def stored_artifacts(self):  # type: ignore[no-untyped-def]
        return self._inner.stored_artifacts

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()


class _FailingAuditFactory:
    def __init__(self, database: EncryptedDatabase) -> None:
        self._database = database

    def unit_of_work(self) -> UnitOfWork:
        inner = cast(UnitOfWork, self._database.unit_of_work())
        return cast(UnitOfWork, _FailingAuditUow(inner))


def _eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def _actor() -> ActorRef:
    return ActorRef(_eid(900), ActorKind.SYSTEM)


def _item(path: Path, value: int, *, minute: int = 0) -> SourceFileImportInput:
    return SourceFileImportInput(
        _eid(value),
        _eid(value + 1000),
        _eid(value + 2000),
        path,
        _NOW + timedelta(minutes=minute),
    )


def _command(*items: SourceFileImportInput) -> ImportSourceFilesCommand:
    return ImportSourceFilesCommand(_eid(100), _actor(), tuple(items))


def _dependency_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except Exception:
        return False
    return True


def _unsupported_code() -> str | None:
    if platform.system() != "Windows" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        return "UNSUPPORTED_PLATFORM"
    if not _dependency_available("sqlcipher3"):
        return "WINDOWS_SQLCIPHER_UNAVAILABLE"
    if not _dependency_available("PIL.Image") or not _dependency_available("pi_heif"):
        return "HEIF_DECODER_UNAVAILABLE"
    return None


def _render_status_lines(statuses: Mapping[str, bool]) -> tuple[str, ...]:
    passed = CURRENT_SCHEMA_VERSION == 5 and all(statuses[name] for name in _CHECKS)
    return (
        f"PR008_VERIFY schema_version={CURRENT_SCHEMA_VERSION}",
        *(f"PR008_VERIFY {name}={'PASS' if statuses[name] else 'FAIL'}" for name in _CHECKS),
        f"PR008_VERIFY result={'PASS' if passed else 'FAIL'}",
    )


def _render_inconclusive_lines(code: str) -> tuple[str, ...]:
    if code not in _INCONCLUSIVE_CODES:
        return ("PR008_VERIFY result=FAIL",)
    return (f"PR008_VERIFY result=INCONCLUSIVE code={code}",)


def _has_allowlisted_shape(lines: tuple[str, ...]) -> bool:
    if len(lines) == 1:
        return lines in tuple(
            (f"PR008_VERIFY result=INCONCLUSIVE code={code}",) for code in _INCONCLUSIVE_CODES
        ) or lines == ("PR008_VERIFY result=FAIL",)
    if len(lines) != len(_CHECKS) + 2 or lines[0] != "PR008_VERIFY schema_version=5":
        return False
    for name, line in zip(_CHECKS, lines[1:-1], strict=True):
        if line not in {f"PR008_VERIFY {name}=PASS", f"PR008_VERIFY {name}=FAIL"}:
            return False
    expected_result = "PASS" if all(line.endswith("=PASS") for line in lines[1:-1]) else "FAIL"
    return lines[-1] == f"PR008_VERIFY result={expected_result}"


def _privacy_safe(
    lines: tuple[str, ...],
    *,
    forbidden_values: tuple[str, ...],
) -> bool:
    if not _has_allowlisted_shape(lines):
        return False
    rendered = "\n".join(lines)
    if any(marker in rendered for marker in _GENERIC_FORBIDDEN_OUTPUT):
        return False
    if _LOWER_SHA256.search(rendered) is not None:
        return False
    return not any(value and value in rendered for value in forbidden_values)


def _generated_image_bytes(format_name: str, *, variant: int = 0, quality: int = 90) -> bytes:
    image_module = importlib.import_module("PIL.Image")
    image = image_module.new("RGB", (32, 24), (245, 245, 245))
    for x in range(32):
        for y in range(24):
            image.putpixel(
                (x, y),
                ((x * 7 + variant) % 256, (y * 11 + variant) % 256, ((x + y) * 5) % 256),
            )
    stream = io.BytesIO()
    kwargs = {"quality": quality} if format_name == "JPEG" else {}
    image.save(stream, format=format_name, **kwargs)
    return stream.getvalue()


def _migration_chain_is_current() -> bool:
    return (
        CURRENT_SCHEMA_VERSION == 5
        and tuple(migration.checksum for migration in MIGRATIONS) == _EXPECTED_MIGRATION_CHECKSUMS
        and (V0001, V0002, V0003, V0004, V0005) == MIGRATIONS
        and V0004.checksum == "a826d5bc07ba73e6d54fd25e9df8afb42028261040b7981bdd157caf26b1f7c6"
        and V0005.checksum == "74f6376fbfd42ed4b9748cadd936daba3c26755a04ddc7cedee76ed2143d95f2"
    )


def _ordinary_sqlite_rejects(path: Path) -> bool:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path)
        connection.execute(_SQLITE_PROBE).fetchall()
    except sqlite3.DatabaseError:
        return True
    finally:
        if connection is not None:
            connection.close()
    return False


def _warning_codes(result: ImportedSourceFileResult) -> tuple[ImportWarningCode, ...]:
    return tuple(warning.code for warning in result.warnings)


def _run_supported() -> _VerificationRun:
    statuses = {name: False for name in _CHECKS}
    temporary = Path(tempfile.mkdtemp(prefix="pr008-verify-"))
    forbidden_values = [
        str(temporary),
        str(_FIXTURE),
        _FIXTURE.name,
        repr(_DATABASE_KEY),
        _DATABASE_KEY.hex(),
        _DATABASE_KEY.decode("ascii"),
        repr(_STORAGE_KEY),
        _STORAGE_KEY.hex(),
        _STORAGE_KEY.decode("ascii"),
        _SQLITE_PROBE,
    ]
    unexpected_failure = False
    try:
        database_path = temporary / "verification.db"
        storage_root = temporary / "managed"
        forbidden_values.extend((str(database_path), str(storage_root)))
        storage_root.mkdir()
        database = EncryptedDatabase(database_path, _DatabaseKeyProvider())
        database.initialize()
        factory = cast(UnitOfWorkFactory, database)
        storage = ImmutableFilesystemStorage(storage_root, _StorageKeyProvider())
        decoder = PillowMediaDecoder()
        statuses["migration_v0004"] = _migration_chain_is_current()
        create_upload_batch(
            CreateUploadBatchCommand(_eid(100), BatchNumber("VERIFY-PR008"), _NOW, _actor()),
            unit_of_work_factory=factory,
        )

        jpeg_bytes = _generated_image_bytes("JPEG", quality=91)
        png_bytes = _generated_image_bytes("PNG")
        similar_bytes = _generated_image_bytes("JPEG", quality=82)
        heif_bytes = _FIXTURE.read_bytes()
        jpeg_path = temporary / "synthetic.JpG"
        png_path = temporary / "synthetic.png"
        heif_path = temporary / "synthetic.HEIC"
        mismatch_path = temporary / "mismatch.png"
        similar_path = temporary / "similar.jpeg"
        unsupported_path = temporary / "unsupported.webp"
        corrupt_path = temporary / "corrupt.jpg"
        for path, content in (
            (jpeg_path, jpeg_bytes),
            (png_path, png_bytes),
            (heif_path, heif_bytes),
            (mismatch_path, jpeg_bytes),
            (similar_path, similar_bytes),
            (unsupported_path, png_bytes),
            (corrupt_path, b"synthetic-corrupt"),
        ):
            path.write_bytes(content)

        source_paths = (
            jpeg_path,
            png_path,
            heif_path,
            mismatch_path,
            similar_path,
            unsupported_path,
            corrupt_path,
        )
        forbidden_values.extend(str(path) for path in source_paths)
        forbidden_values.extend(path.name for path in source_paths)
        original_contents = (
            jpeg_bytes,
            png_bytes,
            heif_bytes,
            similar_bytes,
            b"synthetic-corrupt",
        )
        forbidden_values.extend(
            hashlib.sha256(content).hexdigest() for content in original_contents
        )

        primary_items = (_item(jpeg_path, 1), _item(png_path, 2), _item(heif_path, 3))
        primary_command = _command(*primary_items)
        primary = import_source_files(
            primary_command,
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        forbidden_values.extend(
            entry.source_file.perceptual_hash.hex_value for entry in primary.imported
        )
        media = {entry.source_file.detected_media_type for entry in primary.imported}
        statuses["media_jpeg"] = SourceMediaType.JPEG in media
        statuses["media_png"] = SourceMediaType.PNG in media
        statuses["media_heif"] = SourceMediaType.HEIF in media
        statuses["extension_casefold"] = len(primary.imported) == 3 and not primary.failed

        mismatch = import_source_files(
            _command(_item(mismatch_path, 4)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        statuses["extension_mismatch_warning"] = len(
            mismatch.imported
        ) == 1 and ImportWarningCode.EXTENSION_CONTENT_MISMATCH in _warning_codes(
            mismatch.imported[0]
        )
        unsupported = import_source_files(
            _command(_item(unsupported_path, 5)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        statuses["unsupported_extension"] = (
            len(unsupported.failed) == 1
            and unsupported.failed[0].error_code is SourceImportErrorCode.UNSUPPORTED_EXTENSION
        )
        corrupt = import_source_files(
            _command(_item(corrupt_path, 6)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        statuses["unsupported_extension"] &= (
            len(corrupt.failed) == 1
            and corrupt.failed[0].error_code is SourceImportErrorCode.DECODE_FAILED
        )

        threshold_content = _generated_image_bytes("PNG", variant=47)
        threshold_path = temporary / "threshold-candidate.png"
        threshold_path.write_bytes(threshold_content)
        forbidden_values.extend(
            (
                str(threshold_path),
                threshold_path.name,
                hashlib.sha256(threshold_content).hexdigest(),
            )
        )
        with database.unit_of_work() as uow:
            baseline = uow.source_files.get(_eid(1))
            threshold_batch = uow.upload_batches.get(_eid(100))
        if baseline is None or threshold_batch is None:
            raise RuntimeError("deterministic baseline missing")
        incoming_hash = baseline.perceptual_hash.hex_value
        distance_nine_hash = f"{int(incoming_hash, 16) ^ ((1 << 9) - 1):016x}"
        forbidden_values.extend((incoming_hash, distance_nine_hash))
        distance_nine_proven = dhash64_hamming_distance(incoming_hash, distance_nine_hash) == 9
        threshold_artifact = storage.publish_bytes(
            artifact_id=_eid(1012),
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=threshold_content,
            created_at=_NOW + timedelta(minutes=12),
        )
        threshold_source = SourceFile(
            id=_eid(12),
            batch_id=_eid(100),
            original_artifact_id=_eid(1012),
            original_basename=SourceBasename(threshold_path.name),
            detected_media_type=SourceMediaType.PNG,
            byte_size=len(threshold_content),
            sha256=Sha256Digest(hashlib.sha256(threshold_content).hexdigest()),
            perceptual_hash=PerceptualHash("DHASH64", 1, 64, distance_nine_hash),
            width=32,
            height=24,
            exif_orientation=None,
            imported_at=_NOW + timedelta(minutes=12),
            imported_by=_actor(),
        )
        if threshold_source.sha256 == baseline.sha256:
            raise RuntimeError("deterministic candidate digest collision")
        with database.unit_of_work() as uow:
            current_batch = uow.upload_batches.get(_eid(100))
            if current_batch is None:
                raise RuntimeError("deterministic batch missing")
            uow.stored_artifacts.add(threshold_artifact)
            uow.source_files.add(threshold_source)
            uow.upload_batches.update(current_batch.append_source_file_id(threshold_source.id))
            uow.commit()

        exact_path = temporary / "exact.jpg"
        exact_path.write_bytes(jpeg_bytes)
        forbidden_values.extend((str(exact_path), exact_path.name))
        exact = import_source_files(
            _command(_item(exact_path, 7)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        forbidden_values.extend(
            entry.source_file.perceptual_hash.hex_value for entry in exact.imported
        )
        exact_codes = _warning_codes(exact.imported[0])
        statuses["exact_duplicate"] = ImportWarningCode.EXACT_DUPLICATE in exact_codes
        distance_nine_excluded = distance_nine_proven and not any(
            warning.code is ImportWarningCode.PERCEPTUAL_SIMILARITY
            and warning.related_source_file_id == threshold_source.id
            for warning in exact.imported[0].warnings
        )
        statuses["no_self_match"] = all(
            warning.related_source_file_id != exact.imported[0].source_file.id
            for warning in exact.imported[0].warnings
        )
        similar = import_source_files(
            _command(_item(similar_path, 8)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        forbidden_values.extend(
            entry.source_file.perceptual_hash.hex_value for entry in similar.imported
        )
        perceptual = [
            warning
            for warning in similar.imported[0].warnings
            if warning.code is ImportWarningCode.PERCEPTUAL_SIMILARITY
        ]
        statuses["perceptual_duplicate"] = distance_nine_excluded and bool(
            perceptual
            and all(
                warning.perceptual_distance is not None and warning.perceptual_distance <= 8
                for warning in perceptual
            )
        )
        warning_keys = [
            (
                0 if warning.code is ImportWarningCode.EXACT_DUPLICATE else 1,
                warning.perceptual_distance or 0,
                ""
                if warning.related_source_file_id is None
                else str(warning.related_source_file_id),
            )
            for warning in exact.imported[0].warnings
            if warning.code is not ImportWarningCode.EXTENSION_CONTENT_MISMATCH
        ]
        statuses["warning_order"] = warning_keys == sorted(warning_keys)

        partial_good = temporary / "partial.png"
        partial_bad = temporary / "partial.exe"
        partial_good_bytes = _generated_image_bytes("PNG", variant=13)
        partial_bad_bytes = b"synthetic"
        partial_good.write_bytes(partial_good_bytes)
        partial_bad.write_bytes(partial_bad_bytes)
        forbidden_values.extend(
            (
                str(partial_good),
                partial_good.name,
                str(partial_bad),
                partial_bad.name,
                hashlib.sha256(partial_good_bytes).hexdigest(),
                hashlib.sha256(partial_bad_bytes).hexdigest(),
            )
        )
        partial = import_source_files(
            _command(_item(partial_good, 9), _item(partial_bad, 10)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        statuses["partial_success"] = (
            len(partial.imported) == 1
            and len(partial.failed) == 1
            and partial.failed[0].error_code is SourceImportErrorCode.UNSUPPORTED_EXTENSION
        )
        forbidden_values.extend(
            entry.source_file.perceptual_hash.hex_value for entry in partial.imported
        )

        with database.unit_of_work() as uow:
            first = uow.source_files.get(_eid(1))
            expected = uow.stored_artifacts.get(_eid(1001))
            event = uow.audit_events.get(_eid(2001))
            committed_batch = uow.upload_batches.get(primary_command.batch_id)
        statuses["byte_identity"] = (
            first is not None
            and expected is not None
            and storage.read_bytes(expected=expected) == jpeg_bytes
        )
        statuses["audit_atomicity"] = (
            first is not None
            and expected is not None
            and committed_batch is not None
            and first.id in committed_batch.source_file_ids
            and first.original_artifact_id == expected.artifact_id
            and event is not None
            and event.event_id == primary_items[0].audit_event_id
            and event.occurred_at == primary_items[0].imported_at
            and event.actor == primary_command.actor
            and event.action_code is AuditAction.ARTIFACT_REGISTERED
            and event.subject_type is AuditSubjectType.STORED_ARTIFACT
            and event.subject_id == primary_items[0].artifact_id
            and event.field_key is None
            and event.before is not None
            and event.before.classification is AuditValueClassification.ABSENT
            and event.before.display_value is None
            and event.before.was_present is False
            and event.after is not None
            and event.after.classification is AuditValueClassification.NON_SENSITIVE
            and event.after.display_value == "ORIGINAL"
            and event.after.was_present is True
            and event.reason_code is not None
            and event.reason_code.value == "SOURCE_FILE_IMPORT"
            and event.correlation_id == primary_command.batch_id
        )

        orphan_path = temporary / "orphan.png"
        orphan_bytes = _generated_image_bytes("PNG", variant=29)
        orphan_path.write_bytes(orphan_bytes)
        forbidden_values.extend(
            (
                str(orphan_path),
                orphan_path.name,
                hashlib.sha256(orphan_bytes).hexdigest(),
            )
        )
        orphan_result = import_source_files(
            _command(_item(orphan_path, 11)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=cast(UnitOfWorkFactory, _FailingAuditFactory(database)),
        )
        with database.unit_of_work() as uow:
            expected_records = uow.stored_artifacts.list_all()
            rolled_back_source = uow.source_files.get(_eid(11))
            rolled_back_artifact = uow.stored_artifacts.get(_eid(1011))
            rolled_back_audit = uow.audit_events.get(_eid(2011))
            batch_after_rollback = uow.upload_batches.get(_eid(100))
        objects_before_reconcile = tuple(sorted(storage_root.rglob("*.diosobj")))
        reconciliation = storage.reconcile(expected=expected_records)
        objects_after_reconcile = tuple(sorted(storage_root.rglob("*.diosobj")))
        orphan_reported = any(item.artifact_id == _eid(1011) for item in reconciliation.orphan)
        statuses["orphan_reconciliation"] = (
            len(orphan_result.failed) == 1
            and orphan_result.failed[0].error_code is SourceImportErrorCode.PERSISTENCE_FAILED
            and rolled_back_source is None
            and rolled_back_artifact is None
            and rolled_back_audit is None
            and batch_after_rollback is not None
            and _eid(11) not in batch_after_rollback.source_file_ids
            and orphan_reported
            and objects_before_reconcile == objects_after_reconcile
        )
        statuses["audit_atomicity"] &= statuses["orphan_reconciliation"]

        object_files = tuple(storage_root.rglob("*.diosobj"))
        forbidden_values.extend(str(path) for path in object_files)
        plaintext_values = (
            jpeg_bytes,
            png_bytes,
            heif_bytes,
            similar_bytes,
            threshold_content,
            partial_good_bytes,
            partial_bad_bytes,
            orphan_bytes,
        )
        statuses["encrypted_storage"] = (
            _ordinary_sqlite_rejects(database_path)
            and bool(object_files)
            and all(path.read_bytes().startswith(b"DIOSOBJ1") for path in object_files)
            and all(
                plaintext not in path.read_bytes()
                for path in object_files
                for plaintext in plaintext_values
            )
        )
    except Exception as error:
        unexpected_failure = True
        if str(error):
            forbidden_values.append(str(error))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return _VerificationRun(statuses, tuple(forbidden_values), unexpected_failure)


def main() -> int:
    unsupported = _unsupported_code()
    if unsupported is not None:
        lines = _render_inconclusive_lines(unsupported)
        sys.stdout.write("\n".join(lines) + "\n")
        return 2 if unsupported in _INCONCLUSIVE_CODES else 1
    try:
        run = _run_supported()
    except Exception:
        sys.stdout.write("PR008_VERIFY result=FAIL\n")
        return 1
    statuses = dict(run.statuses)
    privacy_candidate = dict(statuses)
    privacy_candidate["privacy"] = True
    statuses["privacy"] = not run.unexpected_failure and _privacy_safe(
        _render_status_lines(privacy_candidate),
        forbidden_values=run.forbidden_values,
    )
    lines = _render_status_lines(statuses)
    sys.stdout.write("\n".join(lines) + "\n")
    passed = CURRENT_SCHEMA_VERSION == 5 and all(statuses.values())
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
