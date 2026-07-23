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
EXPECTED_PR008_SUCCESS_LINES = (
    "PR008_VERIFY schema_version=6",
    "PR008_VERIFY migration_v0004=PASS",
    "PR008_VERIFY encrypted_storage=PASS",
    "PR008_VERIFY byte_identity=PASS",
    "PR008_VERIFY media_jpeg=PASS",
    "PR008_VERIFY media_png=PASS",
    "PR008_VERIFY media_heif=PASS",
    "PR008_VERIFY extension_casefold=PASS",
    "PR008_VERIFY extension_mismatch_warning=PASS",
    "PR008_VERIFY unsupported_extension=PASS",
    "PR008_VERIFY exact_duplicate=PASS",
    "PR008_VERIFY perceptual_duplicate=PASS",
    "PR008_VERIFY no_self_match=PASS",
    "PR008_VERIFY warning_order=PASS",
    "PR008_VERIFY partial_success=PASS",
    "PR008_VERIFY audit_atomicity=PASS",
    "PR008_VERIFY orphan_reconciliation=PASS",
    "PR008_VERIFY privacy=PASS",
    "PR008_VERIFY result=PASS",
)
FORBIDDEN_PR008_OUTPUT_MARKERS = (
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
        import_command(tmp_path / "bad\n.jpg"),
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
    assert event.before.display_value is None
    assert event.before.was_present is False
    assert event.after is not None
    assert event.after.classification is AuditValueClassification.NON_SENSITIVE
    assert event.after.display_value == "ORIGINAL"
    assert event.after.was_present is True
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


def test_pr008_verifier_subprocess_has_exact_platform_output() -> None:
    repository = Path(__file__).parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/verify_pr008_import.py"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    lines = tuple(completed.stdout.splitlines())
    assert not any(marker in completed.stdout for marker in FORBIDDEN_PR008_OUTPUT_MARKERS)
    if platform.system() == "Windows":
        assert completed.returncode == 0
        assert lines == EXPECTED_PR008_SUCCESS_LINES
    else:
        assert completed.returncode == 2
        assert lines == ("PR008_VERIFY result=INCONCLUSIVE code=UNSUPPORTED_PLATFORM",)


def test_pr008_supported_success_renderer_is_exact(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import verify_pr008_import as verifier

    statuses = {name: True for name in verifier._CHECKS}
    statuses["privacy"] = False
    run = verifier._VerificationRun(statuses, (), False)
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(verifier, "_run_supported", lambda: run)
    assert verifier.main() == 0
    captured = capsys.readouterr()
    assert tuple(captured.out.splitlines()) == EXPECTED_PR008_SUCCESS_LINES
    assert captured.err == ""


@pytest.mark.parametrize(
    "code",
    [
        "WINDOWS_SQLCIPHER_UNAVAILABLE",
        "HEIF_DECODER_UNAVAILABLE",
        "UNSUPPORTED_PLATFORM",
    ],
)
def test_pr008_inconclusive_renderer_is_exact_and_allowlisted(code: str) -> None:
    from scripts import verify_pr008_import as verifier

    lines = verifier._render_inconclusive_lines(code)
    assert lines == (f"PR008_VERIFY result=INCONCLUSIVE code={code}",)
    assert verifier._has_allowlisted_shape(lines)
    assert verifier._privacy_safe(lines, forbidden_values=())


def test_pr008_unknown_inconclusive_code_is_controlled_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import verify_pr008_import as verifier

    monkeypatch.setattr(verifier, "_unsupported_code", lambda: "UNRECOGNIZED")
    assert verifier.main() == 1
    captured = capsys.readouterr()
    assert captured.out == "PR008_VERIFY result=FAIL\n"
    assert captured.err == ""


def test_pr008_supported_real_flow_proves_distance_nine_exclusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import verify_pr008_import as verifier
    from tests.persistence.test_unit_of_work import open_sqlite

    from document_intake.persistence import database

    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    monkeypatch.setattr(verifier, "_ordinary_sqlite_rejects", lambda _path: True)
    run = verifier._run_supported()
    assert run.unexpected_failure is False
    assert run.statuses["perceptual_duplicate"] is True
    assert run.statuses["audit_atomicity"] is True


@pytest.mark.parametrize(
    ("injected", "forbidden_values"),
    [
        ("/private/tmp/pr008-verify", ("/private/tmp/pr008-verify",)),
        ("synthetic-secret.jpg", ("synthetic-secret.jpg",)),
        ("a" * 64, ()),
        ("0123456789abcdef", ("0123456789abcdef",)),
        ("SELECT secret FROM synthetic", ()),
        ("Traceback Exception", ()),
    ],
)
def test_pr008_privacy_helper_rejects_injected_values_and_markers(
    injected: str,
    forbidden_values: tuple[str, ...],
) -> None:
    from scripts import verify_pr008_import as verifier

    lines = list(EXPECTED_PR008_SUCCESS_LINES)
    lines[0] = f"{lines[0]} {injected}"
    assert not verifier._privacy_safe(tuple(lines), forbidden_values=forbidden_values)


def test_pr008_deterministic_product_failure_is_exit_one_and_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import verify_pr008_import as verifier

    statuses = {name: True for name in verifier._CHECKS}
    statuses["media_jpeg"] = False
    statuses["privacy"] = False
    run = verifier._VerificationRun(statuses, (), False)
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(verifier, "_run_supported", lambda: run)
    assert verifier.main() == 1
    captured = capsys.readouterr()
    lines = tuple(captured.out.splitlines())
    assert len(lines) == len(EXPECTED_PR008_SUCCESS_LINES)
    assert lines[0] == "PR008_VERIFY schema_version=6"
    assert "PR008_VERIFY media_jpeg=FAIL" in lines
    assert "PR008_VERIFY privacy=PASS" in lines
    assert lines[-1] == "PR008_VERIFY result=FAIL"
    assert verifier._has_allowlisted_shape(lines)
    assert captured.err == ""


def test_pr008_unexpected_failure_is_sanitized_and_privacy_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import verify_pr008_import as verifier

    statuses = {name: False for name in verifier._CHECKS}
    run = verifier._VerificationRun(statuses, ("unsafe raw exception detail",), True)
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(verifier, "_run_supported", lambda: run)
    assert verifier.main() == 1
    captured = capsys.readouterr()
    lines = tuple(captured.out.splitlines())
    assert lines[-2:] == (
        "PR008_VERIFY privacy=FAIL",
        "PR008_VERIFY result=FAIL",
    )
    assert "unsafe raw exception detail" not in captured.out
    assert verifier._has_allowlisted_shape(lines)
    assert captured.err == ""


def test_pr008_unhandled_supported_failure_is_one_line_sanitized_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import verify_pr008_import as verifier

    def fail_verification() -> verifier._VerificationRun:
        raise RuntimeError("unsafe deterministic exception detail")

    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(verifier, "_run_supported", fail_verification)
    assert verifier.main() == 1
    captured = capsys.readouterr()
    assert captured.out == "PR008_VERIFY result=FAIL\n"
    assert "unsafe deterministic exception detail" not in captured.out
    assert captured.err == ""
