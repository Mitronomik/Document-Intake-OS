"""Sanitized production-component verifier for PR-009 quality assessment."""

from __future__ import annotations

import importlib
import io
import platform
import shutil
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from typing import Self, cast
from uuid import UUID

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
    QualityMetricCode,
    QualityMetricUnit,
)
from document_intake.domain.image_quality import (
    ImageQualityPolicy,
    ImageQualitySeverityRule,
    QualityPolicyVersion,
)
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import BatchNumber
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder, dhash64
from document_intake.image_pipeline.quality_assessor import (
    calculate_quality_metrics,
    evaluate_quality_policy,
)
from document_intake.persistence import CURRENT_SCHEMA_VERSION, EncryptedDatabase
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.migrations.v0005_image_quality import MIGRATION as V0005
from document_intake.storage.filesystem import ImmutableFilesystemStorage

_CHECKS = (
    "schema_version",
    "migration_v0005",
    "import_decoder_compat",
    "quality_decoder",
    "metrics",
    "persistence",
    "audit",
    "rollback",
    "privacy",
)
_DATABASE_KEY = b"Q" * 32
_STORAGE_KEY = b"R" * 32
_NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
_EXPECTED_DHASH = "0000000000000000"
_EXPECTED_GRAYSCALE = bytes((10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120))
_EXPECTED_METRICS = (
    (
        QualityMetricCode.SHORT_SIDE_PIXELS,
        "RESOLUTION_V1",
        1,
        Decimal("3"),
        QualityMetricUnit.PIXELS,
    ),
    (
        QualityMetricCode.LONG_SIDE_PIXELS,
        "RESOLUTION_V1",
        1,
        Decimal("4"),
        QualityMetricUnit.PIXELS,
    ),
    (
        QualityMetricCode.LAPLACIAN_VARIANCE,
        "BLUR_LAPLACIAN_V1",
        1,
        Decimal("0.000000"),
        QualityMetricUnit.VARIANCE,
    ),
    (
        QualityMetricCode.LUMINANCE_STANDARD_DEVIATION,
        "CONTRAST_STDDEV_V1",
        1,
        Decimal("34.520525"),
        QualityMetricUnit.LUMA_LEVEL,
    ),
    (
        QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION,
        "GLARE_CLIPPED_FRACTION_V1",
        1,
        Decimal("0E-8"),
        QualityMetricUnit.FRACTION,
    ),
    (
        QualityMetricCode.SHADOW_CLIPPED_FRACTION,
        "EXPOSURE_CLIPPED_FRACTION_V1",
        1,
        Decimal("0E-8"),
        QualityMetricUnit.FRACTION,
    ),
    (
        QualityMetricCode.BRIGHT_CLIPPED_FRACTION,
        "EXPOSURE_CLIPPED_FRACTION_V1",
        1,
        Decimal("0E-8"),
        QualityMetricUnit.FRACTION,
    ),
)


@dataclass(frozen=True, slots=True)
class VerificationRun:
    statuses: dict[str, bool]
    unsupported: bool = False


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

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()


class _FailingAuditFactory:
    def __init__(self, database: EncryptedDatabase) -> None:
        self._database = database

    def unit_of_work(self) -> UnitOfWork:
        return cast(UnitOfWork, _FailingAuditUow(cast(UnitOfWork, self._database.unit_of_work())))


def _eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def _actor() -> ActorRef:
    return ActorRef(_eid(900), ActorKind.SYSTEM)


def _dependency_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except Exception:
        return False
    return True


def _unsupported() -> bool:
    return platform.system() != "Windows" or not _dependency_available("sqlcipher3")


def _policy() -> ImageQualityPolicy:
    return ImageQualityPolicy(
        QualityPolicyVersion("TEST_PR009", 1),
        3,
        4,
        Decimal("0.000000"),
        Decimal("10.000000"),
        200,
        Decimal("0.50000000"),
        5,
        Decimal("0.50000000"),
        200,
        Decimal("0.50000000"),
        tuple(
            ImageQualitySeverityRule(code, QualityIssueSeverity.WARNING)
            for code in QualityIssueCode
        ),
    )


def _synthetic_png() -> bytes:
    image_module = importlib.import_module("PIL.Image")
    image = image_module.new("RGB", (4, 3))
    values = list(_EXPECTED_GRAYSCALE)
    for y in range(3):
        for x in range(4):
            v = values[y * 4 + x]
            image.putpixel((x, y), (v, v, v))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _object_set(root: Path) -> tuple[bytes, ...]:
    return tuple(sorted(p.read_bytes() for p in root.rglob("*.diosobj") if p.is_file()))


def _stored_ids(database: EncryptedDatabase) -> tuple[str, ...]:
    with database.unit_of_work() as uow:
        return tuple(str(r.artifact_id) for r in uow.stored_artifacts.list_all())


def _render(statuses: Mapping[str, bool]) -> tuple[str, ...]:
    return (
        "PR009_VERIFY schema_version=5",
        *(f"PR009_VERIFY {name}={'PASS' if statuses[name] else 'FAIL'}" for name in _CHECKS[1:]),
        f"PR009_VERIFY result={'PASS' if all(statuses[name] for name in _CHECKS) else 'FAIL'}",
    )


def _assert_decoder_and_metrics(content: bytes, decoder: PillowMediaDecoder) -> bool:
    imported = decoder.decode_for_import(content=content)
    decoded = decoder.decode_for_quality(content=content)
    metrics = calculate_quality_metrics(decoded)
    observed = tuple(
        (m.metric_code, m.algorithm_id, m.algorithm_version, m.numeric_value, m.unit)
        for m in metrics
    )
    status, issues = evaluate_quality_policy(metrics, _policy())
    return (
        imported.grayscale_width == 9
        and imported.grayscale_height == 8
        and dhash64(imported.grayscale_pixels) == _EXPECTED_DHASH
        and decoded.encoded_width == 4
        and decoded.encoded_height == 3
        and decoded.exif_orientation is None
        and decoded.effective_width == 4
        and decoded.effective_height == 3
        and decoded.grayscale_width == 4
        and decoded.grayscale_height == 3
        and decoded.grayscale_pixels == _EXPECTED_GRAYSCALE
        and observed == _EXPECTED_METRICS
        and status is QualityAssessmentStatus.GOOD
        and issues == ()
    )


def _corruption_rejected(database: EncryptedDatabase, assessment_id: EntityId) -> bool:
    with database.unit_of_work() as uow:
        repo = uow.image_quality_assessments
        repo._execute("DROP TRIGGER image_quality_metrics_no_update")
        repo._execute(
            (
                "UPDATE image_quality_metrics SET canonical_payload='{}' "
                "WHERE assessment_id=? AND ordinal=0"
            ),
            (str(assessment_id),),
        )
        uow.commit()
    try:
        with database.unit_of_work() as uow:
            uow.image_quality_assessments.get(assessment_id)
    except PersistenceError as error:
        return error.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
    return False


def run_supported() -> VerificationRun:
    if _unsupported():
        return VerificationRun({name: False for name in _CHECKS}, unsupported=True)
    statuses = {name: False for name in _CHECKS}
    temporary = Path(tempfile.mkdtemp(prefix="pr009-verify-"))
    try:
        db = EncryptedDatabase(temporary / "verification.db", _DatabaseKeyProvider())
        db.initialize()
        storage_root = temporary / "storage"
        storage_root.mkdir()
        storage = ImmutableFilesystemStorage(storage_root, _StorageKeyProvider())
        decoder = PillowMediaDecoder()
        factory = cast(UnitOfWorkFactory, db)
        content = _synthetic_png()
        original_plaintext = bytes(content)
        source_path = temporary / "source.png"
        source_path.write_bytes(content)
        statuses["schema_version"] = CURRENT_SCHEMA_VERSION == 5
        statuses["migration_v0005"] = (
            MIGRATIONS[-1] == V0005
            and V0005.checksum == "74f6376fbfd42ed4b9748cadd936daba3c26755a04ddc7cedee76ed2143d95f2"
        )
        statuses["quality_decoder"] = _assert_decoder_and_metrics(content, decoder)
        statuses["metrics"] = statuses["quality_decoder"]
        create_upload_batch(
            CreateUploadBatchCommand(_eid(100), BatchNumber("VERIFY-PR009"), _NOW, _actor()),
            unit_of_work_factory=factory,
        )
        import_result = import_source_files(
            ImportSourceFilesCommand(
                _eid(100),
                _actor(),
                (SourceFileImportInput(_eid(200), _eid(300), _eid(400), source_path, _NOW),),
            ),
            storage=storage,
            media_decoder=decoder,
            unit_of_work_factory=factory,
        )
        source = import_result.imported[0].source_file if import_result.imported else None
        before_ids = _stored_ids(db)
        before_objects = _object_set(storage_root)
        statuses["import_decoder_compat"] = source is not None and statuses["quality_decoder"]
        command = AssessSourceFileQualityCommand(
            _eid(200), _eid(500), _eid(600), _NOW, _actor(), _policy(), _eid(700)
        )
        result = assess_source_file_quality(
            command, decoder=decoder, storage=storage, unit_of_work_factory=factory
        )
        after_ids = _stored_ids(db)
        after_objects = _object_set(storage_root)
        with db.unit_of_work() as uow:
            stored = (
                uow.stored_artifacts.get(source.original_artifact_id)
                if source is not None
                else None
            )
            persisted = uow.image_quality_assessments.get(command.assessment_id)
            listed = uow.image_quality_assessments.list_by_source(command.source_file_id)
            audit_events = uow.audit_events.list_by_correlation(command.correlation_id)
        statuses["persistence"] = (
            result.assessment == persisted
            and listed == (result.assessment,)
            and len(result.assessment.metrics) == 7
            and result.assessment.issues == ()
            and result.assessment.policy == command.policy
            and before_ids == after_ids
            and before_objects == after_objects
            and stored is not None
            and storage.read_bytes(expected=stored) == original_plaintext
        )
        event = audit_events[0] if len(audit_events) == 1 else None
        statuses["audit"] = (
            event is not None
            and event.event_id == command.audit_event_id
            and event.occurred_at == command.assessed_at
            and event.actor == command.actor
            and event.action_code is AuditAction.IMAGE_QUALITY_ASSESSED
            and event.subject_type is AuditSubjectType.IMAGE_QUALITY_ASSESSMENT
            and event.subject_id == command.assessment_id
            and event.field_key is None
            and event.before is not None
            and event.before.classification is AuditValueClassification.ABSENT
            and event.before.display_value is None
            and event.before.was_present is False
            and event.after is not None
            and event.after.classification is AuditValueClassification.NON_SENSITIVE
            and event.after.display_value == "QUALITY_ASSESSMENT"
            and event.after.was_present is True
            and event.reason_code is not None
            and str(event.reason_code) == "IMAGE_QUALITY_ASSESSMENT"
            and event.correlation_id == command.correlation_id
        )
        failed = AssessSourceFileQualityCommand(
            _eid(200), _eid(501), _eid(601), _NOW, _actor(), _policy(), _eid(701)
        )
        try:
            assess_source_file_quality(
                failed,
                decoder=decoder,
                storage=storage,
                unit_of_work_factory=cast(UnitOfWorkFactory, _FailingAuditFactory(db)),
            )
        except QualityAssessmentError as error:
            rollback_error_ok = error.code is QualityAssessmentErrorCode.PERSISTENCE_FAILED
        else:
            rollback_error_ok = False
        with db.unit_of_work() as uow:
            failed_absent = uow.image_quality_assessments.get(failed.assessment_id) is None
            success_present = (
                uow.image_quality_assessments.get(command.assessment_id) == result.assessment
            )
            failed_audit_absent = uow.audit_events.get(failed.audit_event_id) is None
        statuses["rollback"] = (
            rollback_error_ok
            and failed_absent
            and success_present
            and failed_audit_absent
            and before_ids == _stored_ids(db)
            and before_objects == _object_set(storage_root)
        )
        statuses["privacy"] = content == original_plaintext and _corruption_rejected(
            db, command.assessment_id
        )
    except Exception:
        return VerificationRun(statuses)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return VerificationRun(statuses)


def main() -> int:
    run = run_supported()
    if run.unsupported:
        return 2
    lines = _render(run.statuses)
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if all(run.statuses.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
