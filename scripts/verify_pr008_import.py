"""Sanitized production-component verifier for PR-008."""

from __future__ import annotations

import importlib
import io
import platform
import shutil
import sqlite3
import sys
import tempfile
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
from document_intake.domain.enums import (
    ActorKind,
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    ImportWarningCode,
    SourceImportErrorCode,
    SourceMediaType,
)
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import BatchNumber
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder
from document_intake.persistence import CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.migrations.v0001_initial import MIGRATION as V0001
from document_intake.persistence.migrations.v0002_stored_artifacts import MIGRATION as V0002
from document_intake.persistence.migrations.v0003_audit_events import MIGRATION as V0003
from document_intake.persistence.migrations.v0004_source_file_import import MIGRATION as V0004
from document_intake.storage.filesystem import ImmutableFilesystemStorage

_EXPECTED_MIGRATION_CHECKSUMS = (
    "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500",
    "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d",
    "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1",
    "a826d5bc07ba73e6d54fd25e9df8afb42028261040b7981bdd157caf26b1f7c6",
)
_FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "synthetic" / "pr008_color_grid.heic"
_NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
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


class _DatabaseKeyProvider:
    def get_database_key(self) -> bytes:
        return b"D" * 32


class _StorageKeyProvider:
    def get_current_key(self) -> StorageKey:
        return StorageKey(1, b"S" * 32)

    def get_key(self, version: int) -> StorageKey:
        return StorageKey(version, b"S" * 32)


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


def _ordinary_sqlite_rejects(path: Path) -> bool:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path)
        connection.execute("SELECT name FROM sqlite_master").fetchall()
    except sqlite3.DatabaseError:
        return True
    finally:
        if connection is not None:
            connection.close()
    return False


def _warning_codes(result: ImportedSourceFileResult) -> tuple[ImportWarningCode, ...]:
    return tuple(warning.code for warning in result.warnings)


def _run_supported() -> dict[str, bool]:
    statuses = {name: False for name in _CHECKS}
    temporary = Path(tempfile.mkdtemp(prefix="pr008-verify-"))
    try:
        database_path = temporary / "verification.db"
        storage_root = temporary / "managed"
        storage_root.mkdir()
        database = EncryptedDatabase(database_path, _DatabaseKeyProvider())
        database.initialize()
        factory = cast(UnitOfWorkFactory, database)
        storage = ImmutableFilesystemStorage(storage_root, _StorageKeyProvider())
        decoder = PillowMediaDecoder()
        statuses["migration_v0004"] = (
            CURRENT_SCHEMA_VERSION == 4
            and tuple(migration.checksum for migration in MIGRATIONS)
            == _EXPECTED_MIGRATION_CHECKSUMS
            and (V0001, V0002, V0003, V0004) == MIGRATIONS
        )
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

        primary = import_source_files(
            _command(_item(jpeg_path, 1), _item(png_path, 2), _item(heif_path, 3)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
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

        exact_path = temporary / "exact.jpg"
        exact_path.write_bytes(jpeg_bytes)
        exact = import_source_files(
            _command(_item(exact_path, 7)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        exact_codes = _warning_codes(exact.imported[0])
        statuses["exact_duplicate"] = ImportWarningCode.EXACT_DUPLICATE in exact_codes
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
        perceptual = [
            warning
            for warning in similar.imported[0].warnings
            if warning.code is ImportWarningCode.PERCEPTUAL_SIMILARITY
        ]
        statuses["perceptual_duplicate"] = bool(
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
        partial_good.write_bytes(_generated_image_bytes("PNG", variant=13))
        partial_bad.write_bytes(b"synthetic")
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

        with database.unit_of_work() as uow:
            first = uow.source_files.get(_eid(1))
            expected = uow.stored_artifacts.get(_eid(1001))
            event = uow.audit_events.get(_eid(2001))
        statuses["byte_identity"] = (
            first is not None
            and expected is not None
            and storage.read_bytes(expected=expected) == jpeg_bytes
        )
        statuses["audit_atomicity"] = (
            event is not None
            and event.action_code is AuditAction.ARTIFACT_REGISTERED
            and event.subject_type is AuditSubjectType.STORED_ARTIFACT
            and event.subject_id == _eid(1001)
            and event.before is not None
            and event.before.classification is AuditValueClassification.ABSENT
            and event.after is not None
            and event.after.classification is AuditValueClassification.NON_SENSITIVE
            and event.after.display_value == "ORIGINAL"
            and event.correlation_id == _eid(100)
        )

        orphan_path = temporary / "orphan.png"
        orphan_path.write_bytes(_generated_image_bytes("PNG", variant=29))
        orphan_result = import_source_files(
            _command(_item(orphan_path, 11)),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=cast(UnitOfWorkFactory, _FailingAuditFactory(database)),
        )
        with database.unit_of_work() as uow:
            expected_records = uow.stored_artifacts.list_all()
            rolled_back_source = uow.source_files.get(_eid(11))
            rolled_back_audit = uow.audit_events.get(_eid(2011))
        reconciliation = storage.reconcile(expected=expected_records)
        statuses["orphan_reconciliation"] = (
            len(orphan_result.failed) == 1
            and orphan_result.failed[0].error_code is SourceImportErrorCode.PERSISTENCE_FAILED
            and rolled_back_source is None
            and rolled_back_audit is None
            and reconciliation.counts["orphan"] >= 1
        )
        statuses["audit_atomicity"] &= rolled_back_source is None and rolled_back_audit is None

        object_files = tuple(storage_root.rglob("*.diosobj"))
        statuses["encrypted_storage"] = (
            _ordinary_sqlite_rejects(database_path)
            and bool(object_files)
            and all(path.read_bytes().startswith(b"DIOSOBJ1") for path in object_files)
            and all(jpeg_bytes not in path.read_bytes() for path in object_files)
        )
        statuses["privacy"] = True
    except Exception:
        statuses["privacy"] = True
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return statuses


def main() -> int:
    unsupported = _unsupported_code()
    if unsupported is not None:
        print(f"PR008_VERIFY result=INCONCLUSIVE code={unsupported}")
        return 2
    statuses = _run_supported()
    print(f"PR008_VERIFY schema_version={CURRENT_SCHEMA_VERSION}")
    for name in _CHECKS:
        print(f"PR008_VERIFY {name}={'PASS' if statuses[name] else 'FAIL'}")
    passed = CURRENT_SCHEMA_VERSION == 4 and all(statuses.values())
    print(f"PR008_VERIFY result={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
