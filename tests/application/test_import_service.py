from __future__ import annotations

import platform
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from document_intake.application.dto.imports import (
    CreateUploadBatchCommand,
    ImportSourceFilesCommand,
    SourceFileImportInput,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.media import DecodedMedia
from document_intake.application.services import imports as service_module
from document_intake.application.services.imports import create_upload_batch, import_source_files
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.entities.imports import SourceFile, UploadBatch
from document_intake.domain.enums import (
    ActorKind,
    ArtifactKind,
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    ImportWarningCode,
    SourceImportErrorCode,
    SourceMediaType,
    UploadBatchStatus,
)
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import (
    BatchNumber,
    PerceptualHash,
    Sha256Digest,
    SourceBasename,
)
from document_intake.image_pipeline.media_decoder import MediaDecodeError
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
PIXELS = bytes(range(9)) * 8


def eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def actor(value: int = 900) -> ActorRef:
    return ActorRef(eid(value), ActorKind.OPERATOR)


def decoded(
    media_type: SourceMediaType = SourceMediaType.JPEG,
    pixels: bytes = PIXELS,
) -> DecodedMedia:
    return DecodedMedia(media_type, 32, 24, None, pixels, 9, 8)


def source_file(
    value: int,
    *,
    batch_id: EntityId | None = None,
    artifact_id: EntityId | None = None,
    sha: str = "a" * 64,
    phash: str = "0000000000000000",
    imported_at: datetime = NOW,
) -> SourceFile:
    return SourceFile(
        id=eid(value),
        batch_id=batch_id or eid(100),
        original_artifact_id=artifact_id or eid(value + 1000),
        original_basename=SourceBasename("synthetic.jpg"),
        detected_media_type=SourceMediaType.JPEG,
        byte_size=3,
        sha256=Sha256Digest(sha),
        perceptual_hash=PerceptualHash("DHASH64", 1, 64, phash),
        width=32,
        height=24,
        exif_orientation=None,
        imported_at=imported_at,
        imported_by=actor(),
    )


@dataclass
class State:
    batches: dict[EntityId, UploadBatch] = field(default_factory=dict)
    sources: dict[EntityId, SourceFile] = field(default_factory=dict)
    artifacts: dict[EntityId, StoredArtifactRecord] = field(default_factory=dict)
    audits: dict[EntityId, AuditEvent] = field(default_factory=dict)


class BatchRepo:
    def __init__(self, uow: FakeUow) -> None:
        self.uow = uow

    def add(self, batch: UploadBatch) -> None:
        if batch.id in self.uow.working.batches or self.get_by_number(batch.number) is not None:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        self.uow.working.batches[batch.id] = batch

    def get(self, batch_id: EntityId) -> UploadBatch | None:
        if self.uow.factory.fail_initial_lookup:
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)
        return self.uow.working.batches.get(batch_id)

    def get_by_number(self, number: BatchNumber) -> UploadBatch | None:
        return next(
            (batch for batch in self.uow.working.batches.values() if batch.number == number),
            None,
        )

    def update(self, batch: UploadBatch) -> None:
        self.uow.working.batches[batch.id] = batch


class SourceRepo:
    def __init__(self, uow: FakeUow) -> None:
        self.uow = uow

    def add(self, value: SourceFile) -> None:
        if value.id in self.uow.working.sources or any(
            item.original_artifact_id == value.original_artifact_id
            for item in self.uow.working.sources.values()
        ):
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        self.uow.working.sources[value.id] = value

    def get(self, source_file_id: EntityId) -> SourceFile | None:
        return self.uow.working.sources.get(source_file_id)

    def list_by_sha256(self, sha256: Sha256Digest) -> tuple[SourceFile, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in (
                        *self.uow.working.sources.values(),
                        *self.uow.factory.lookup_only_sources.values(),
                    )
                    if item.sha256 == sha256
                ),
                key=lambda item: (item.imported_at, str(item.id)),
            )
        )

    def list_compatible_perceptual_hashes(
        self,
        algorithm_id: str,
        algorithm_version: int,
        bit_width: int,
    ) -> tuple[SourceFile, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in (
                        *self.uow.working.sources.values(),
                        *self.uow.factory.lookup_only_sources.values(),
                    )
                    if (
                        item.perceptual_hash.algorithm_id,
                        item.perceptual_hash.algorithm_version,
                        item.perceptual_hash.bit_width,
                    )
                    == (algorithm_id, algorithm_version, bit_width)
                ),
                key=lambda item: (item.imported_at, str(item.id)),
            )
        )


class ArtifactRepo:
    def __init__(self, uow: FakeUow) -> None:
        self.uow = uow

    def add(self, value: StoredArtifactRecord) -> None:
        if value.artifact_id in self.uow.working.artifacts:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        self.uow.working.artifacts[value.artifact_id] = value

    def get(self, artifact_id: EntityId) -> StoredArtifactRecord | None:
        return self.uow.working.artifacts.get(artifact_id)


class AuditRepo:
    def __init__(self, uow: FakeUow) -> None:
        self.uow = uow

    def add(self, value: AuditEvent) -> None:
        if self.uow.factory.fail_audit:
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)
        self.uow.working.audits[value.event_id] = value


class FakeUow:
    def __init__(self, factory: Factory) -> None:
        self.factory = factory
        self.working = deepcopy(factory.state)
        self.upload_batches = BatchRepo(self)
        self.source_files = SourceRepo(self)
        self.stored_artifacts = ArtifactRepo(self)
        self.audit_events = AuditRepo(self)
        self.committed = False

    def __enter__(self) -> Self:
        self.factory.opened += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if not self.committed:
            self.factory.rollbacks += 1
        return False

    def commit(self) -> None:
        if self.factory.fail_commit:
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)
        self.factory.state = self.working
        self.factory.commits += 1
        self.committed = True

    def rollback(self) -> None:
        self.factory.rollbacks += 1


@dataclass
class Factory:
    state: State = field(default_factory=State)
    opened: int = 0
    commits: int = 0
    rollbacks: int = 0
    fail_initial_lookup: bool = False
    fail_commit: bool = False
    fail_audit: bool = False
    lookup_only_sources: dict[EntityId, SourceFile] = field(default_factory=dict)

    def unit_of_work(self) -> FakeUow:
        return FakeUow(self)


class Decoder:
    def __init__(
        self,
        result: DecodedMedia | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.result = result or decoded()
        self.error = error
        self.calls: list[bytes] = []

    def decode_for_import(self, *, content: bytes) -> DecodedMedia:
        self.calls.append(content)
        if self.error is not None:
            raise self.error
        return self.result


class Storage:
    def __init__(self, *, fail: bool = False, wrong_id: bool = False) -> None:
        self.fail = fail
        self.wrong_id = wrong_id
        self.published: list[tuple[EntityId, ArtifactKind, bytes, datetime]] = []

    def publish_bytes(
        self,
        *,
        artifact_id: EntityId,
        artifact_kind: ArtifactKind,
        plaintext: bytes,
        created_at: datetime,
    ) -> StoredArtifactRecord:
        if self.fail:
            raise RuntimeError("unsafe raw storage failure")
        self.published.append((artifact_id, artifact_kind, plaintext, created_at))
        returned_id = eid(9999) if self.wrong_id else artifact_id
        return StoredArtifactRecord(
            artifact_id=returned_id,
            artifact_kind=artifact_kind,
            object_generation=1,
            plaintext_length=len(plaintext),
            plaintext_sha256="a" * 64,
            ciphertext_sha256="b" * 64,
            key_version=1,
            storage_format_version=1,
            created_at=created_at,
        )


def batch_command(value: int = 100, number: str = "BATCH-100") -> CreateUploadBatchCommand:
    return CreateUploadBatchCommand(eid(value), BatchNumber(number), NOW, actor())


def item(path: Path, value: int = 1) -> SourceFileImportInput:
    return SourceFileImportInput(eid(value), eid(value + 1000), eid(value + 2000), path, NOW)


def import_command(path: Path, value: int = 1) -> ImportSourceFilesCommand:
    return ImportSourceFilesCommand(eid(100), actor(), (item(path, value),))


def ready_factory() -> Factory:
    factory = Factory()
    batch = create_upload_batch(batch_command(), unit_of_work_factory=factory)
    assert batch.status is UploadBatchStatus.NEW
    return factory


def write_source(
    tmp_path: Path, name: str = "synthetic.jpg", content: bytes = b"raw-original"
) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_create_upload_batch_success_and_duplicate_id_or_number() -> None:
    factory = Factory()
    batch = create_upload_batch(batch_command(), unit_of_work_factory=factory)
    assert batch == factory.state.batches[eid(100)]
    assert factory.commits == 1
    with pytest.raises(PersistenceError) as duplicate_id:
        create_upload_batch(batch_command(number="OTHER"), unit_of_work_factory=factory)
    assert duplicate_id.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    with pytest.raises(PersistenceError) as duplicate_number:
        create_upload_batch(batch_command(101), unit_of_work_factory=factory)
    assert duplicate_number.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS


def test_missing_batch_and_initial_persistence_failure_do_not_read_files(tmp_path: Path) -> None:
    path = tmp_path / "missing.jpg"
    missing = import_source_files(
        import_command(path),
        storage=Storage(),
        media_decoder=Decoder(),
        unit_of_work_factory=Factory(),
    )
    assert missing.failed[0].error_code is SourceImportErrorCode.BATCH_NOT_FOUND
    failing = Factory(fail_initial_lookup=True)
    result = import_source_files(
        import_command(path),
        storage=Storage(),
        media_decoder=Decoder(),
        unit_of_work_factory=failing,
    )
    assert result.failed[0].error_code is SourceImportErrorCode.PERSISTENCE_FAILED


@pytest.mark.parametrize(
    ("name", "media_type"),
    [
        ("grid.JpG", SourceMediaType.JPEG),
        ("grid.JPEG", SourceMediaType.JPEG),
        ("grid.PnG", SourceMediaType.PNG),
        ("grid.HEIC", SourceMediaType.HEIF),
        ("grid.HeIf", SourceMediaType.HEIF),
    ],
)
def test_supported_extensions_are_casefolded(
    tmp_path: Path, name: str, media_type: SourceMediaType
) -> None:
    factory = ready_factory()
    result = import_source_files(
        import_command(write_source(tmp_path, name)),
        storage=Storage(),
        media_decoder=Decoder(decoded(media_type)),
        unit_of_work_factory=factory,
    )
    assert result.failed == ()
    assert result.imported[0].source_file.detected_media_type is media_type


@pytest.mark.parametrize("name", ["synthetic", "synthetic.", "synthetic.webp", "a.jpg.exe"])
def test_unsupported_extension_fails_before_decode_and_storage(tmp_path: Path, name: str) -> None:
    factory = ready_factory()
    decoder = Decoder()
    storage = Storage()
    result = import_source_files(
        import_command(write_source(tmp_path, name)),
        storage=storage,
        media_decoder=decoder,
        unit_of_work_factory=factory,
    )
    assert result.failed[0].error_code is SourceImportErrorCode.UNSUPPORTED_EXTENSION
    assert decoder.calls == []
    assert storage.published == []


def test_basename_validation_and_file_read_failures(tmp_path: Path) -> None:
    factory = ready_factory()
    invalid = import_source_files(
        import_command(write_source(tmp_path, "bad\n.jpg")),
        storage=Storage(),
        media_decoder=Decoder(),
        unit_of_work_factory=factory,
    )
    assert invalid.failed[0].error_code is SourceImportErrorCode.SOURCE_BASENAME_INVALID
    missing = import_source_files(
        import_command(tmp_path / "gone.jpg"),
        storage=Storage(),
        media_decoder=Decoder(),
        unit_of_work_factory=factory,
    )
    assert missing.failed[0].error_code is SourceImportErrorCode.SOURCE_READ_FAILED
    directory = tmp_path / "folder.jpg"
    directory.mkdir()
    not_file = import_source_files(
        import_command(directory),
        storage=Storage(),
        media_decoder=Decoder(),
        unit_of_work_factory=factory,
    )
    assert not_file.failed[0].error_code is SourceImportErrorCode.SOURCE_READ_FAILED


def test_changed_file_during_read_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = ready_factory()
    path = write_source(tmp_path)
    snapshots = [
        service_module._ReadSnapshot(12, 1, 1),
        service_module._ReadSnapshot(12, 2, 1),
    ]
    monkeypatch.setattr(service_module, "_safe_stat", lambda _path: snapshots.pop(0))
    result = import_source_files(
        import_command(path),
        storage=Storage(),
        media_decoder=Decoder(),
        unit_of_work_factory=factory,
    )
    assert result.failed[0].error_code is SourceImportErrorCode.SOURCE_READ_FAILED


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            MediaDecodeError(SourceImportErrorCode.UNSUPPORTED_FORMAT),
            SourceImportErrorCode.UNSUPPORTED_FORMAT,
        ),
        (
            MediaDecodeError(SourceImportErrorCode.DECODE_FAILED),
            SourceImportErrorCode.DECODE_FAILED,
        ),
        (RuntimeError("unsafe decoder detail"), SourceImportErrorCode.DECODE_FAILED),
    ],
)
def test_decoder_errors_are_controlled(
    tmp_path: Path, error: BaseException, expected: SourceImportErrorCode
) -> None:
    result = import_source_files(
        import_command(write_source(tmp_path)),
        storage=Storage(),
        media_decoder=Decoder(error=error),
        unit_of_work_factory=ready_factory(),
    )
    assert result.failed[0].error_code is expected


def test_extension_mismatch_imports_and_preserves_exact_original_bytes(tmp_path: Path) -> None:
    content = b"exact unchanged original bytes"
    storage = Storage()
    result = import_source_files(
        import_command(write_source(tmp_path, "synthetic.png", content)),
        storage=storage,
        media_decoder=Decoder(decoded(SourceMediaType.JPEG)),
        unit_of_work_factory=ready_factory(),
    )
    assert result.failed == ()
    assert [warning.code for warning in result.imported[0].warnings] == [
        ImportWarningCode.EXTENSION_CONTENT_MISMATCH
    ]
    assert storage.published == [(eid(1001), ArtifactKind.ORIGINAL, content, NOW)]


def test_exact_perceptual_threshold_self_exclusion_and_warning_order(tmp_path: Path) -> None:
    factory = ready_factory()
    digest = Sha256Digest(__import__("hashlib").sha256(b"raw-original").hexdigest())
    factory.lookup_only_sources = {
        eid(9): source_file(9, sha=digest.value, phash="0000000000000000"),
        eid(3): source_file(3, sha=digest.value, phash="0000000000000000"),
        eid(7): source_file(7, sha="b" * 64, phash="00000000000000ff"),
        eid(6): source_file(6, sha="c" * 64, phash="00000000000001ff"),
        eid(1): source_file(1, artifact_id=eid(1001), sha="d" * 64, phash="0000000000000001"),
    }
    result = import_source_files(
        import_command(write_source(tmp_path, "synthetic.png")),
        storage=Storage(),
        media_decoder=Decoder(decoded(SourceMediaType.JPEG)),
        unit_of_work_factory=factory,
    )
    warnings = result.imported[0].warnings
    assert [
        (warning.code, warning.related_source_file_id, warning.perceptual_distance)
        for warning in warnings
    ] == [
        (ImportWarningCode.EXACT_DUPLICATE, eid(3), None),
        (ImportWarningCode.EXACT_DUPLICATE, eid(9), None),
        (ImportWarningCode.PERCEPTUAL_SIMILARITY, eid(7), 8),
        (ImportWarningCode.EXTENSION_CONTENT_MISMATCH, None, None),
    ]
    assert eid(6) not in {warning.related_source_file_id for warning in warnings}
    assert eid(1) not in {warning.related_source_file_id for warning in warnings}


@pytest.mark.parametrize(
    ("storage", "factory", "expected"),
    [
        (Storage(fail=True), None, SourceImportErrorCode.STORAGE_PUBLICATION_FAILED),
        (Storage(wrong_id=True), None, SourceImportErrorCode.STORAGE_PUBLICATION_FAILED),
        (Storage(), Factory(), SourceImportErrorCode.PERSISTENCE_FAILED),
    ],
)
def test_storage_and_database_failures_are_sanitized(
    tmp_path: Path,
    storage: Storage,
    factory: Factory | None,
    expected: SourceImportErrorCode,
) -> None:
    actual_factory = factory or ready_factory()
    if factory is not None:
        create_upload_batch(batch_command(), unit_of_work_factory=actual_factory)
        actual_factory.fail_commit = True
    result = import_source_files(
        import_command(write_source(tmp_path)),
        storage=storage,
        media_decoder=Decoder(),
        unit_of_work_factory=actual_factory,
    )
    assert result.failed[0].error_code is expected
    assert actual_factory.state.sources == {}
    assert actual_factory.state.artifacts == {}
    assert actual_factory.state.audits == {}
    if expected is SourceImportErrorCode.PERSISTENCE_FAILED:
        assert len(storage.published) == 1  # encrypted object-first orphan is retained


def test_success_uses_one_atomic_write_transaction_and_exact_audit(tmp_path: Path) -> None:
    factory = ready_factory()
    opened_before = factory.opened
    result = import_source_files(
        import_command(write_source(tmp_path)),
        storage=Storage(),
        media_decoder=Decoder(),
        unit_of_work_factory=factory,
    )
    imported = result.imported[0].source_file
    assert factory.opened - opened_before == 3  # batch check, lookup, one write transaction
    assert factory.commits == 2  # batch creation plus exactly one import commit
    assert factory.state.batches[eid(100)].source_file_ids == (imported.id,)
    event = factory.state.audits[eid(2001)]
    assert event.event_id == eid(2001)
    assert event.action_code is AuditAction.ARTIFACT_REGISTERED
    assert event.subject_type is AuditSubjectType.STORED_ARTIFACT
    assert event.subject_id == eid(1001)
    assert event.actor == actor()
    assert event.occurred_at == NOW
    assert event.field_key is None
    assert event.before is not None
    assert event.before.classification is AuditValueClassification.ABSENT
    assert event.after is not None
    assert event.after.classification is AuditValueClassification.NON_SENSITIVE
    assert event.after.display_value == "ORIGINAL"
    assert event.reason_code is not None and event.reason_code.value == "SOURCE_FILE_IMPORT"
    assert event.correlation_id == eid(100)


def test_audit_failure_rolls_back_all_database_changes_but_retains_orphan(tmp_path: Path) -> None:
    factory = ready_factory()
    factory.fail_audit = True
    storage = Storage()
    result = import_source_files(
        import_command(write_source(tmp_path)),
        storage=storage,
        media_decoder=Decoder(),
        unit_of_work_factory=factory,
    )
    assert result.failed[0].error_code is SourceImportErrorCode.PERSISTENCE_FAILED
    assert factory.state.batches[eid(100)].source_file_ids == ()
    assert factory.state.sources == factory.state.artifacts == factory.state.audits == {}
    assert len(storage.published) == 1


def test_earlier_success_survives_later_failure_and_processing_continues(tmp_path: Path) -> None:
    paths = (
        write_source(tmp_path, "first.jpg", b"one"),
        write_source(tmp_path, "bad.exe", b"two"),
        write_source(tmp_path, "third.png", b"three"),
    )
    command = ImportSourceFilesCommand(
        eid(100), actor(), tuple(item(path, index) for index, path in enumerate(paths, 1))
    )
    factory = ready_factory()
    result = import_source_files(
        command,
        storage=Storage(),
        media_decoder=Decoder(decoded(SourceMediaType.JPEG)),
        unit_of_work_factory=factory,
    )
    assert [entry.source_file.id for entry in result.imported] == [eid(1), eid(3)]
    assert [(entry.source_file_id, entry.error_code) for entry in result.failed] == [
        (eid(2), SourceImportErrorCode.UNSUPPORTED_EXTENSION)
    ]
    assert factory.state.batches[eid(100)].source_file_ids == (eid(1), eid(3))
    assert set(factory.state.audits) == {eid(2001), eid(2003)}


def test_pr008_verifier_subprocess_has_only_controlled_output() -> None:
    repository = Path(__file__).parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/verify_pr008_import.py"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    assert completed.returncode in {0, 2}
    lines = completed.stdout.splitlines()
    assert lines
    assert all(line.startswith("PR008_VERIFY ") for line in lines)
    if platform.system() == "Windows":
        assert completed.returncode == 0
        assert lines[-1] == "PR008_VERIFY result=PASS"
    else:
        assert completed.returncode == 2
        assert lines == ["PR008_VERIFY result=INCONCLUSIVE code=UNSUPPORTED_PLATFORM"]
