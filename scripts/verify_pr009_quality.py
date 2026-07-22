"""Sanitized production-component verifier for PR-009."""

from __future__ import annotations

import importlib
import io
import platform
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID

from PIL import Image

from document_intake.application.dto.image_quality import AssessSourceFileQualityCommand
from document_intake.application.dto.imports import (
    CreateUploadBatchCommand,
    ImportSourceFilesCommand,
    SourceFileImportInput,
)
from document_intake.application.ports.persistence import UnitOfWork, UnitOfWorkFactory
from document_intake.application.ports.storage import StorageKey
from document_intake.application.services.image_quality import (
    QualityAssessmentError,
    assess_source_file_quality,
)
from document_intake.application.services.imports import create_upload_batch, import_source_files
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import (
    ActorKind,
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    QualityAssessmentErrorCode,
    QualityAssessmentStatus,
    QualityIssueCode,
    QualityIssueSeverity,
    SourceMediaType,
)
from document_intake.domain.image_quality import (
    ImageQualityPolicy,
    ImageQualitySeverityRule,
    QualityPolicyVersion,
)
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import BatchNumber
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder, dhash64
from document_intake.persistence import CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.migrations.v0001_initial import MIGRATION as V0001
from document_intake.persistence.migrations.v0002_stored_artifacts import MIGRATION as V0002
from document_intake.persistence.migrations.v0003_audit_events import MIGRATION as V0003
from document_intake.persistence.migrations.v0004_source_file_import import MIGRATION as V0004
from document_intake.persistence.migrations.v0005_image_quality import MIGRATION as V0005
from document_intake.storage.filesystem import ImmutableFilesystemStorage

_CHECKS = (
    "migration_v0005",
    "import_decoder_compat",
    "quality_decoder",
    "metrics",
    "persistence",
    "audit",
    "rollback",
    "privacy",
)
_SUCCESS_LINES = (
    "PR009_VERIFY schema_version=5",
    *(f"PR009_VERIFY {name}=PASS" for name in _CHECKS),
    "PR009_VERIFY result=PASS",
)
_INCONCLUSIVE_CODES = ("UNSUPPORTED_PLATFORM", "WINDOWS_SQLCIPHER_UNAVAILABLE")
_EXPECTED_MIGRATION_CHECKSUMS = (
    "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500",
    "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d",
    "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1",
    "a826d5bc07ba73e6d54fd25e9df8afb42028261040b7981bdd157caf26b1f7c6",
    "6d020d1acfbce3fcb7168e935617f2ae008a32bea7def1f37de84e36e9e2224f",
)
_EXPECTED_IMPORT_GRAYSCALE = (
    b'%&))\x1b\x00\x00\x00\x00"!\x1f\x1e!*4;;$!\x19\x174p\xaa\xd1\xd2HB5/J'
    b"\x8a\xcb\xf7\xf7wsmgdjszujv\x89\xa1\xa4\x89cF87T\x83\xc0\xe6\xd4\xa5|f"
    b"\x15;y\xca\xff\xff\xd2\xa6\x8c"
)
_EXPECTED_DHASH64 = "18e0e0e0f10f0f07"
_EXPECTED_QUALITY_GRAYSCALE = b"$\x1d\x00,@\xff|\x80LE\xfa\x96"
_EXPECTED_ENCODED_DIMENSIONS = (4, 3)
_EXPECTED_EFFECTIVE_DIMENSIONS = (3, 4)
_EXPECTED_EXIF_ORIENTATION = 6
_EXPECTED_METRICS = (
    ("SHORT_SIDE_PIXELS", "RESOLUTION_V1", 1, "3", "PIXELS"),
    ("LONG_SIDE_PIXELS", "RESOLUTION_V1", 1, "4", "PIXELS"),
    ("LAPLACIAN_VARIANCE", "BLUR_LAPLACIAN_V1", 1, "9801.000000", "VARIANCE"),
    (
        "LUMINANCE_STANDARD_DEVIATION",
        "CONTRAST_STDDEV_V1",
        1,
        "79.287933",
        "LUMA_LEVEL",
    ),
    (
        "HIGHLIGHT_CLIPPED_FRACTION",
        "GLARE_CLIPPED_FRACTION_V1",
        1,
        "0.16666667",
        "FRACTION",
    ),
    (
        "SHADOW_CLIPPED_FRACTION",
        "EXPOSURE_CLIPPED_FRACTION_V1",
        1,
        "0.16666667",
        "FRACTION",
    ),
    (
        "BRIGHT_CLIPPED_FRACTION",
        "EXPOSURE_CLIPPED_FRACTION_V1",
        1,
        "0.16666667",
        "FRACTION",
    ),
)
_EXPECTED_ISSUES = (
    ("LOW_RESOLUTION", "BLOCKING"),
    ("LOW_CONTRAST", "WARNING"),
)
_NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
_DATABASE_KEY = b"Q" * 32
_STORAGE_KEY = b"R" * 32
_GENERIC_FORBIDDEN_OUTPUT = (
    "/private/",
    "/tmp/",
    "\\",
    ".db",
    ".png",
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


@dataclass(frozen=True, slots=True)
class _Run:
    statuses: dict[str, bool]
    forbidden_values: tuple[str, ...] = ()
    unexpected_failure: bool = False


class _DatabaseKeyProvider:
    def get_database_key(self) -> bytes:
        return _DATABASE_KEY


class _StorageKeyProvider:
    def get_current_key(self) -> StorageKey:
        return StorageKey(1, _STORAGE_KEY)

    def get_key(self, version: int) -> StorageKey:
        return StorageKey(version, _STORAGE_KEY)


class _FailingAuditRepository:
    def add(self, event: AuditEvent) -> None:
        del event
        raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)


class _FailingAuditUnitOfWork:
    def __init__(self, inner: UnitOfWork) -> None:
        self._inner = inner
        self.audit_events = _FailingAuditRepository()

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
    def source_files(self):  # type: ignore[no-untyped-def]
        return self._inner.source_files

    @property
    def stored_artifacts(self):  # type: ignore[no-untyped-def]
        return self._inner.stored_artifacts

    @property
    def image_quality_assessments(self):  # type: ignore[no-untyped-def]
        return self._inner.image_quality_assessments

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()


class _FailingAuditFactory:
    def __init__(self, database: EncryptedDatabase) -> None:
        self._database = database

    def unit_of_work(self) -> UnitOfWork:
        inner = cast(UnitOfWork, self._database.unit_of_work())
        return cast(UnitOfWork, _FailingAuditUnitOfWork(inner))


def _eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def _actor() -> ActorRef:
    return ActorRef(_eid(900), ActorKind.SYSTEM)


def _policy() -> ImageQualityPolicy:
    return ImageQualityPolicy(
        QualityPolicyVersion("SYNTHETIC_PR009", 1),
        4,
        5,
        Decimal("1000.000000"),
        Decimal("80.000000"),
        200,
        Decimal("0.20000000"),
        30,
        Decimal("0.20000000"),
        220,
        Decimal("0.20000000"),
        tuple(
            ImageQualitySeverityRule(
                code,
                QualityIssueSeverity.BLOCKING
                if code in {QualityIssueCode.LOW_RESOLUTION, QualityIssueCode.BLUR_DETECTED}
                else QualityIssueSeverity.WARNING,
            )
            for code in QualityIssueCode
        ),
    )


def _synthetic_png() -> bytes:
    image = Image.new("RGB", (4, 3))
    image.putdata(
        [
            (0, 0, 0),
            (255, 255, 255),
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (64, 64, 64),
            (128, 128, 128),
            (250, 250, 250),
            (20, 40, 60),
            (60, 40, 20),
            (10, 200, 30),
            (200, 10, 30),
        ]
    )
    exif = Image.Exif()
    exif[274] = _EXPECTED_EXIF_ORIENTATION
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", exif=exif)
    return buffer.getvalue()


def _synthetic_mpo(*, primary_variant: int, secondary_variant: int) -> bytes:
    primary = Image.new("RGB", (18, 12))
    primary.putdata(
        [
            (
                (x * 29 + y * 7 + primary_variant * 31) % 256,
                (x * 5 + y * 37 + primary_variant * 17) % 256,
                (x * 19 + y * 11 + primary_variant * 43) % 256,
            )
            for y in range(12)
            for x in range(18)
        ]
    )
    secondary_size = (9, 7) if secondary_variant % 2 else (25, 21)
    secondary = Image.new("RGB", secondary_size)
    secondary.putdata(
        [
            (
                (x * 41 + secondary_variant * 13) % 256,
                (y * 23 + secondary_variant * 47) % 256,
                ((x + y) * 31 + secondary_variant * 19) % 256,
            )
            for y in range(secondary_size[1])
            for x in range(secondary_size[0])
        ]
    )
    exif = Image.Exif()
    exif[274] = 6
    buffer = io.BytesIO()
    primary.save(
        buffer,
        format="MPO",
        save_all=True,
        append_images=[secondary],
        quality=95,
        subsampling=0,
        exif=exif,
    )
    return buffer.getvalue()


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
    return None


def _render(statuses: Mapping[str, bool]) -> tuple[str, ...]:
    passed = CURRENT_SCHEMA_VERSION == 5 and all(statuses[name] for name in _CHECKS)
    return (
        f"PR009_VERIFY schema_version={CURRENT_SCHEMA_VERSION}",
        *(f"PR009_VERIFY {name}={'PASS' if statuses[name] else 'FAIL'}" for name in _CHECKS),
        f"PR009_VERIFY result={'PASS' if passed else 'FAIL'}",
    )


def _render_inconclusive(code: str) -> tuple[str, ...]:
    if code not in _INCONCLUSIVE_CODES:
        return ("PR009_VERIFY result=FAIL",)
    return (f"PR009_VERIFY result=INCONCLUSIVE code={code}",)


def _has_allowlisted_shape(lines: tuple[str, ...]) -> bool:
    if len(lines) == 1:
        return lines == ("PR009_VERIFY result=FAIL",) or lines in tuple(
            (f"PR009_VERIFY result=INCONCLUSIVE code={code}",) for code in _INCONCLUSIVE_CODES
        )
    if len(lines) != len(_CHECKS) + 2 or lines[0] != "PR009_VERIFY schema_version=5":
        return False
    for name, line in zip(_CHECKS, lines[1:-1], strict=True):
        if line not in {f"PR009_VERIFY {name}=PASS", f"PR009_VERIFY {name}=FAIL"}:
            return False
    expected = "PASS" if all(line.endswith("=PASS") for line in lines[1:-1]) else "FAIL"
    return lines[-1] == f"PR009_VERIFY result={expected}"


def _privacy_safe(lines: tuple[str, ...], *, forbidden_values: tuple[str, ...]) -> bool:
    if not _has_allowlisted_shape(lines):
        return False
    rendered = "\n".join(lines)
    if any(marker in rendered for marker in _GENERIC_FORBIDDEN_OUTPUT):
        return False
    if _LOWER_SHA256.search(rendered) is not None:
        return False
    return not any(value and value in rendered for value in forbidden_values)


def _metric_vector(assessment: Any) -> tuple[tuple[str, str, int, str, str], ...]:
    return tuple(
        (
            metric.metric_code.value,
            metric.algorithm_id,
            metric.algorithm_version,
            str(metric.numeric_value),
            metric.unit.value,
        )
        for metric in assessment.metrics
    )


def _issue_vector(assessment: Any) -> tuple[tuple[str, str], ...]:
    return tuple((issue.issue_code.value, issue.severity.value) for issue in assessment.issues)


def _row_count(repository: Any, table: str, assessment_id: EntityId) -> int:
    rows = repository._fetchall(
        f"SELECT count(*) FROM {table} WHERE assessment_id=?",
        (str(assessment_id),),
    )
    return int(rows[0][0])


def _quality_command(value: int, source_id: EntityId, *, minute: int = 0):  # type: ignore[no-untyped-def]
    return AssessSourceFileQualityCommand(
        source_file_id=source_id,
        assessment_id=_eid(value),
        audit_event_id=_eid(value + 100),
        assessed_at=_NOW + timedelta(minutes=minute),
        actor=_actor(),
        policy=_policy(),
        correlation_id=_eid(600),
    )


def _verify_mpo_production_flow(
    temporary: Path,
) -> tuple[bool, bool, bool, tuple[str, ...]]:
    database_path = temporary / "multi-frame-quality.db"
    storage_root = temporary / "multi-frame-managed"
    storage_root.mkdir()
    contents = (
        _synthetic_mpo(primary_variant=1, secondary_variant=1),
        _synthetic_mpo(primary_variant=1, secondary_variant=2),
        _synthetic_mpo(primary_variant=2, secondary_variant=1),
    )
    paths = (
        temporary / "multi-frame-a.jpg",
        temporary / "multi-frame-b.jpeg",
        temporary / "multi-frame-c.JPG",
    )
    for path, content in zip(paths, contents, strict=True):
        path.write_bytes(content)

    database = EncryptedDatabase(database_path, _DatabaseKeyProvider())
    database.initialize()
    factory = cast(UnitOfWorkFactory, database)
    storage = ImmutableFilesystemStorage(storage_root, _StorageKeyProvider())
    decoder = PillowMediaDecoder()
    batch_id = _eid(700)
    create_upload_batch(
        CreateUploadBatchCommand(batch_id, BatchNumber("VERIFY-MPO"), _NOW, _actor()),
        unit_of_work_factory=factory,
    )
    import_result = import_source_files(
        ImportSourceFilesCommand(
            batch_id,
            _actor(),
            tuple(
                SourceFileImportInput(
                    _eid(source_value),
                    _eid(artifact_value),
                    _eid(audit_value),
                    path,
                    _NOW + timedelta(minutes=index),
                )
                for index, (path, source_value, artifact_value, audit_value) in enumerate(
                    zip(paths, (701, 702, 703), (801, 802, 803), (901, 902, 903), strict=True)
                )
            ),
        ),
        storage=storage,
        media_decoder=decoder,
        unit_of_work_factory=factory,
    )
    sources = tuple(entry.source_file for entry in import_result.imported)
    decoded = tuple(decoder.decode_for_quality(content=content) for content in contents)
    pillow_mpo = []
    for content in contents:
        with Image.open(io.BytesIO(content)) as image:
            pillow_mpo.append(image.format == "MPO" and getattr(image, "n_frames", 1) == 2)

    assessments = tuple(
        assess_source_file_quality(
            _quality_command(1001 + index, source.id, minute=10 + index),
            decoder=decoder,
            storage=storage,
            unit_of_work_factory=factory,
        ).assessment
        for index, source in enumerate(sources)
    )
    with database.unit_of_work() as uow:
        artifacts = tuple(uow.stored_artifacts.get(_eid(value)) for value in (801, 802, 803))
    stored_bytes_unchanged = all(
        artifact is not None and storage.read_bytes(expected=artifact) == content
        for artifact, content in zip(artifacts, contents, strict=True)
    )
    import_ok = (
        len(sources) == 3
        and not import_result.failed
        and all(source.detected_media_type is SourceMediaType.JPEG for source in sources)
        and sources[0].perceptual_hash == sources[1].perceptual_hash
        and sources[0].perceptual_hash != sources[2].perceptual_hash
        and stored_bytes_unchanged
        and all(path.read_bytes() == content for path, content in zip(paths, contents, strict=True))
    )
    quality_ok = (
        all(pillow_mpo)
        and all(media.media_type is SourceMediaType.JPEG for media in decoded)
        and all((media.encoded_width, media.encoded_height) == (18, 12) for media in decoded)
        and all((media.effective_width, media.effective_height) == (12, 18) for media in decoded)
        and all(media.exif_orientation == 6 for media in decoded)
        and decoded[0].grayscale_pixels == decoded[1].grayscale_pixels
        and decoded[0].grayscale_pixels != decoded[2].grayscale_pixels
    )
    metric_vectors = tuple(_metric_vector(assessment) for assessment in assessments)
    metrics_ok = (
        all(len(vector) == 7 for vector in metric_vectors)
        and metric_vectors[0] == metric_vectors[1]
        and metric_vectors[0] != metric_vectors[2]
    )
    forbidden = (
        str(database_path),
        str(storage_root),
        *(str(path) for path in paths),
        *(path.name for path in paths),
        *(source.sha256.value for source in sources),
        *(source.perceptual_hash.hex_value for source in sources),
    )
    return import_ok, quality_ok, metrics_ok, forbidden


def _run_supported() -> _Run:
    statuses = dict.fromkeys(_CHECKS, False)
    temporary = Path(tempfile.mkdtemp(prefix="pr009-verify-"))
    forbidden_values = [
        str(temporary),
        repr(_DATABASE_KEY),
        _DATABASE_KEY.hex(),
        _DATABASE_KEY.decode("ascii"),
        repr(_STORAGE_KEY),
        _STORAGE_KEY.hex(),
        _STORAGE_KEY.decode("ascii"),
    ]
    unexpected_failure = False
    try:
        mpo_import_ok, mpo_quality_ok, mpo_metrics_ok, mpo_forbidden = _verify_mpo_production_flow(
            temporary
        )
        forbidden_values.extend(mpo_forbidden)
        database_path = temporary / "quality.db"
        storage_root = temporary / "managed"
        storage_root.mkdir()
        source_path = temporary / "synthetic-quality.png"
        content = _synthetic_png()
        source_path.write_bytes(content)
        forbidden_values.extend(
            (str(database_path), str(storage_root), str(source_path), source_path.name)
        )

        database = EncryptedDatabase(database_path, _DatabaseKeyProvider())
        database.initialize()
        factory = cast(UnitOfWorkFactory, database)
        storage = ImmutableFilesystemStorage(storage_root, _StorageKeyProvider())
        decoder = PillowMediaDecoder()
        statuses["migration_v0005"] = (
            CURRENT_SCHEMA_VERSION == 5
            and MIGRATIONS == (V0001, V0002, V0003, V0004, V0005)
            and tuple(migration.checksum for migration in MIGRATIONS)
            == _EXPECTED_MIGRATION_CHECKSUMS
            and V0005.checksum == _EXPECTED_MIGRATION_CHECKSUMS[-1]
        )

        batch_id = _eid(100)
        source_id = _eid(101)
        artifact_id = _eid(201)
        import_audit_id = _eid(301)
        create_upload_batch(
            CreateUploadBatchCommand(
                batch_id,
                BatchNumber("VERIFY-PR009"),
                _NOW,
                _actor(),
            ),
            unit_of_work_factory=factory,
        )
        imported_result = import_source_files(
            ImportSourceFilesCommand(
                batch_id,
                _actor(),
                (
                    SourceFileImportInput(
                        source_id,
                        artifact_id,
                        import_audit_id,
                        source_path,
                        _NOW,
                    ),
                ),
            ),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        if len(imported_result.imported) != 1 or imported_result.failed:
            raise RuntimeError
        imported_source = imported_result.imported[0].source_file
        forbidden_values.extend(
            (
                str(batch_id),
                str(source_id),
                str(artifact_id),
                str(import_audit_id),
                imported_source.sha256.value,
                imported_source.perceptual_hash.hex_value,
            )
        )
        with database.unit_of_work() as uow:
            authoritative_source = uow.source_files.get(source_id)
            authoritative_artifact = uow.stored_artifacts.get(artifact_id)
        if authoritative_source is None or authoritative_artifact is None:
            raise RuntimeError

        object_paths_before = tuple(sorted(storage_root.rglob("*.diosobj")))
        if len(object_paths_before) != 1:
            raise RuntimeError
        encrypted_object_before = object_paths_before[0].read_bytes()
        import_decoded = decoder.decode_for_import(content=content)
        statuses["import_decoder_compat"] = (
            import_decoded.grayscale_pixels == _EXPECTED_IMPORT_GRAYSCALE
            and dhash64(
                import_decoded.grayscale_pixels,
                import_decoded.grayscale_width,
                import_decoded.grayscale_height,
            )
            == _EXPECTED_DHASH64
            and authoritative_source == imported_source
            and imported_source.perceptual_hash.hex_value == _EXPECTED_DHASH64
            and mpo_import_ok
        )
        quality_decoded = decoder.decode_for_quality(content=content)
        statuses["quality_decoder"] = (
            (quality_decoded.encoded_width, quality_decoded.encoded_height)
            == _EXPECTED_ENCODED_DIMENSIONS
            and (quality_decoded.effective_width, quality_decoded.effective_height)
            == _EXPECTED_EFFECTIVE_DIMENSIONS
            and quality_decoded.exif_orientation == _EXPECTED_EXIF_ORIENTATION
            and quality_decoded.grayscale_pixels == _EXPECTED_QUALITY_GRAYSCALE
            and source_path.read_bytes() == content
            and mpo_quality_ok
        )

        first_command = _quality_command(401, source_id)
        first_result = assess_source_file_quality(
            first_command,
            decoder=decoder,
            storage=storage,
            unit_of_work_factory=factory,
        )
        with database.unit_of_work() as uow:
            persisted = uow.image_quality_assessments.get(first_command.assessment_id)
            first_listing = uow.image_quality_assessments.list_by_source(source_id)
            metric_count = _row_count(
                cast(Any, uow.image_quality_assessments),
                "image_quality_metrics",
                first_command.assessment_id,
            )
            issue_count = _row_count(
                cast(Any, uow.image_quality_assessments),
                "image_quality_issues",
                first_command.assessment_id,
            )
            audit_event = uow.audit_events.get(first_command.audit_event_id)
            source_after_success = uow.source_files.get(source_id)
            artifact_after_success = uow.stored_artifacts.get(artifact_id)
        if persisted is None:
            raise RuntimeError
        statuses["metrics"] = (
            _metric_vector(persisted) == _EXPECTED_METRICS
            and _issue_vector(persisted) == _EXPECTED_ISSUES
            and persisted.status is QualityAssessmentStatus.RETAKE_REQUIRED
            and mpo_metrics_ok
        )
        complete_round_trip = (
            persisted == first_result.assessment
            and persisted.policy == first_command.policy
            and metric_count == 7
            and issue_count == len(_EXPECTED_ISSUES)
            and first_listing == (persisted,)
        )
        statuses["audit"] = (
            audit_event is not None
            and audit_event.event_id == first_command.audit_event_id
            and audit_event.occurred_at == first_command.assessed_at
            and audit_event.actor == first_command.actor
            and audit_event.action_code is AuditAction.IMAGE_QUALITY_ASSESSED
            and audit_event.subject_type is AuditSubjectType.IMAGE_QUALITY_ASSESSMENT
            and audit_event.subject_id == first_command.assessment_id
            and audit_event.field_key is None
            and audit_event.before is not None
            and audit_event.before.classification is AuditValueClassification.ABSENT
            and audit_event.before.display_value is None
            and audit_event.before.was_present is False
            and audit_event.after is not None
            and audit_event.after.classification is AuditValueClassification.NON_SENSITIVE
            and audit_event.after.display_value == "QUALITY_ASSESSMENT"
            and audit_event.after.was_present is True
            and audit_event.reason_code is not None
            and audit_event.reason_code.value == "IMAGE_QUALITY_ASSESSMENT"
            and audit_event.correlation_id == first_command.correlation_id
        )

        rollback_command = _quality_command(403, source_id, minute=1)
        rollback_error = None
        try:
            assess_source_file_quality(
                rollback_command,
                decoder=decoder,
                storage=storage,
                unit_of_work_factory=cast(UnitOfWorkFactory, _FailingAuditFactory(database)),
            )
        except QualityAssessmentError as error:
            rollback_error = error
        with database.unit_of_work() as uow:
            rollback_repo = cast(Any, uow.image_quality_assessments)
            rolled_back_assessment = uow.image_quality_assessments.get(
                rollback_command.assessment_id
            )
            rolled_back_metric_count = _row_count(
                rollback_repo,
                "image_quality_metrics",
                rollback_command.assessment_id,
            )
            rolled_back_issue_count = _row_count(
                rollback_repo,
                "image_quality_issues",
                rollback_command.assessment_id,
            )
            rolled_back_audit = uow.audit_events.get(rollback_command.audit_event_id)
            source_after_rollback = uow.source_files.get(source_id)
            artifact_after_rollback = uow.stored_artifacts.get(artifact_id)
        objects_after_rollback = tuple(sorted(storage_root.rglob("*.diosobj")))
        statuses["rollback"] = (
            rollback_error is not None
            and rollback_error.code is QualityAssessmentErrorCode.PERSISTENCE_FAILED
            and rollback_error.__cause__ is None
            and rolled_back_assessment is None
            and rolled_back_metric_count == 0
            and rolled_back_issue_count == 0
            and rolled_back_audit is None
            and source_after_rollback == authoritative_source
            and artifact_after_rollback == authoritative_artifact
            and objects_after_rollback == object_paths_before
            and object_paths_before[0].read_bytes() == encrypted_object_before
        )

        second_command = _quality_command(402, source_id, minute=2)
        second_result = assess_source_file_quality(
            second_command,
            decoder=decoder,
            storage=storage,
            unit_of_work_factory=factory,
        )
        with database.unit_of_work() as uow:
            deterministic_listing = uow.image_quality_assessments.list_by_source(source_id)
        list_is_deterministic = deterministic_listing == (
            first_result.assessment,
            second_result.assessment,
        )

        with database.unit_of_work() as uow:
            corrupting_repository = cast(Any, uow.image_quality_assessments)
            corrupting_repository._execute("DROP TRIGGER image_quality_metrics_no_update")
            corrupting_repository._execute(
                "UPDATE image_quality_metrics SET numeric_value='999' "
                "WHERE assessment_id=? AND ordinal=0",
                (str(first_command.assessment_id),),
            )
            uow.commit()
        corruption_rejected = False
        try:
            with database.unit_of_work() as uow:
                uow.image_quality_assessments.get(first_command.assessment_id)
        except PersistenceError as error:
            corruption_rejected = error.code is PersistenceErrorCode.PERSISTED_DATA_INVALID

        object_paths_after = tuple(sorted(storage_root.rglob("*.diosobj")))
        encrypted_object_after = object_paths_after[0].read_bytes()
        statuses["persistence"] = (
            complete_round_trip
            and list_is_deterministic
            and corruption_rejected
            and source_after_success == authoritative_source
            and artifact_after_success == authoritative_artifact
            and object_paths_after == object_paths_before
            and encrypted_object_after == encrypted_object_before
        )
    except Exception:
        unexpected_failure = True
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return _Run(statuses, tuple(forbidden_values), unexpected_failure)


def main() -> int:
    unsupported = _unsupported_code()
    if unsupported is not None:
        lines = _render_inconclusive(unsupported)
        sys.stdout.write("\n".join(lines) + "\n")
        return 2 if unsupported in _INCONCLUSIVE_CODES else 1
    try:
        run = _run_supported()
    except Exception:
        sys.stdout.write("PR009_VERIFY result=FAIL\n")
        return 1
    statuses = dict(run.statuses)
    privacy_candidate = dict(statuses)
    privacy_candidate["privacy"] = True
    statuses["privacy"] = not run.unexpected_failure and _privacy_safe(
        _render(privacy_candidate),
        forbidden_values=run.forbidden_values,
    )
    lines = _render(statuses)
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if lines == _SUCCESS_LINES else 1


if __name__ == "__main__":
    sys.exit(main())
