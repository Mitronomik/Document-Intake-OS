"""Typed synthetic-only scaffolding for sequential PR-011 evidence workstreams."""
# ruff: noqa: F403, F405

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.entities.imports import SourceFile, UploadBatch
from document_intake.domain.enums import *
from document_intake.domain.image_geometry import *
from document_intake.domain.image_quality import *
from document_intake.domain.prepared_jpeg import *
from document_intake.domain.value_objects import (
    ActorRef,
    AuditReasonCode,
    EntityId,
)
from document_intake.domain.value_objects import (
    Sha256Digest as DomainDigest,
)
from document_intake.domain.value_objects.imports import (
    BatchNumber,
    PerceptualHash,
    Sha256Digest,
    SourceBasename,
)
from document_intake.persistence import database, geometry_serialization
from document_intake.persistence.database import SqlCipherUnitOfWork
from document_intake.persistence.migrations import MIGRATIONS

STAMP = datetime(2026, 7, 26, 12, tzinfo=UTC)


def entity_id(n: int) -> EntityId:
    return EntityId(UUID(int=n))


def actor() -> ActorRef:
    return ActorRef(entity_id(90), ActorKind.SYSTEM)


def correlation_id() -> EntityId:
    return entity_id(91)


def valid_upload_batch() -> UploadBatch:
    return UploadBatch(
        entity_id(10), BatchNumber("BATCH-10"), STAMP, actor(), UploadBatchStatus.NEW, ()
    )


def valid_original_stored_artifact() -> StoredArtifactRecord:
    return StoredArtifactRecord(
        entity_id(11), ArtifactKind.ORIGINAL, 1, 12, "a" * 64, "b" * 64, 1, 1, STAMP
    )


def valid_source_file() -> SourceFile:
    return SourceFile(
        entity_id(20),
        entity_id(10),
        entity_id(11),
        SourceBasename("synthetic.jpg"),
        SourceMediaType.JPEG,
        12,
        Sha256Digest("a" * 64),
        PerceptualHash("DHASH64", 1, 64, "0" * 16),
        32,
        24,
        None,
        STAMP,
        actor(),
    )


def valid_audit_event() -> AuditEvent:
    return AuditEvent(
        entity_id(50),
        STAMP,
        actor(),
        AuditAction.ARTIFACT_REGISTERED,
        AuditSubjectType.STORED_ARTIFACT,
        entity_id(11),
        reason_code=AuditReasonCode("SYSTEM_ACTION"),
        correlation_id=correlation_id(),
    )


def valid_quality_audit_event() -> AuditEvent:
    return AuditEvent(
        entity_id(51),
        STAMP,
        actor(),
        AuditAction.IMAGE_QUALITY_ASSESSED,
        AuditSubjectType.IMAGE_QUALITY_ASSESSMENT,
        entity_id(24),
        reason_code=AuditReasonCode("IMAGE_QUALITY_ASSESSED"),
        correlation_id=correlation_id(),
    )


def valid_geometry_audit_event() -> AuditEvent:
    return AuditEvent(
        entity_id(52),
        STAMP,
        actor(),
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
        entity_id(30),
        reason_code=AuditReasonCode("IMAGE_GEOMETRY_RECIPE_CREATED"),
        correlation_id=correlation_id(),
    )


def _metric(c: QualityMetricCode, v: str) -> ImageQualityMetric:
    alg = {
        QualityMetricCode.SHORT_SIDE_PIXELS: "RESOLUTION_V1",
        QualityMetricCode.LONG_SIDE_PIXELS: "RESOLUTION_V1",
        QualityMetricCode.LAPLACIAN_VARIANCE: "BLUR_LAPLACIAN_V1",
        QualityMetricCode.LUMINANCE_STANDARD_DEVIATION: "CONTRAST_STDDEV_V1",
        QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION: "GLARE_CLIPPED_FRACTION_V1",
        QualityMetricCode.SHADOW_CLIPPED_FRACTION: "EXPOSURE_CLIPPED_FRACTION_V1",
        QualityMetricCode.BRIGHT_CLIPPED_FRACTION: "EXPOSURE_CLIPPED_FRACTION_V1",
    }[c]
    unit = {
        QualityMetricCode.SHORT_SIDE_PIXELS: QualityMetricUnit.PIXELS,
        QualityMetricCode.LONG_SIDE_PIXELS: QualityMetricUnit.PIXELS,
        QualityMetricCode.LAPLACIAN_VARIANCE: QualityMetricUnit.VARIANCE,
        QualityMetricCode.LUMINANCE_STANDARD_DEVIATION: QualityMetricUnit.LUMA_LEVEL,
        QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION: QualityMetricUnit.FRACTION,
        QualityMetricCode.SHADOW_CLIPPED_FRACTION: QualityMetricUnit.FRACTION,
        QualityMetricCode.BRIGHT_CLIPPED_FRACTION: QualityMetricUnit.FRACTION,
    }[c]
    return ImageQualityMetric(c, alg, 1, Decimal(v), unit)


def valid_quality_metrics() -> tuple[ImageQualityMetric, ...]:
    return (
        _metric(QualityMetricCode.SHORT_SIDE_PIXELS, "24"),
        _metric(QualityMetricCode.LONG_SIDE_PIXELS, "32"),
        _metric(QualityMetricCode.LAPLACIAN_VARIANCE, "1.000000"),
        _metric(QualityMetricCode.LUMINANCE_STANDARD_DEVIATION, "1.000000"),
        _metric(QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION, "0.50000000"),
        _metric(QualityMetricCode.SHADOW_CLIPPED_FRACTION, "0.50000000"),
        _metric(QualityMetricCode.BRIGHT_CLIPPED_FRACTION, "0.50000000"),
    )


def valid_quality_issue() -> ImageQualityIssue:
    return _valid_quality_result()[0][0]


def _policy() -> ImageQualityPolicy:
    return ImageQualityPolicy(
        QualityPolicyVersion("TEST_PR009", 1),
        25,
        32,
        Decimal("1"),
        Decimal("1"),
        200,
        Decimal(".5"),
        10,
        Decimal(".5"),
        240,
        Decimal(".5"),
        tuple(ImageQualitySeverityRule(c, QualityIssueSeverity.WARNING) for c in QualityIssueCode),
    )


def valid_quality_assessment() -> ImageQualityAssessment:
    issues, status = _valid_quality_result()
    return ImageQualityAssessment(
        entity_id(24),
        entity_id(20),
        STAMP,
        _policy(),
        status,
        32,
        24,
        None,
        32,
        24,
        valid_quality_metrics(),
        issues,
    )


def _valid_quality_result() -> tuple[tuple[ImageQualityIssue, ...], QualityAssessmentStatus]:
    return derive_quality_issues_and_status(valid_quality_metrics(), _policy())


def valid_geometry_recipe() -> ImageGeometryRecipe:
    return ImageGeometryRecipe(
        entity_id(30),
        entity_id(20),
        None,
        1,
        GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
        32,
        24,
        GeometryQuarterTurn.DEG_0,
        SourceQuadrilateral(
            GeometryPoint(0, 0), GeometryPoint(32, 0), GeometryPoint(32, 24), GeometryPoint(0, 24)
        ),
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        STAMP,
    )


def valid_prepared_stored_artifact() -> StoredArtifactRecord:
    return StoredArtifactRecord(
        entity_id(41), ArtifactKind.PREPARED_JPEG, 1, 64, "c" * 64, "d" * 64, 1, 1, STAMP
    )


def valid_prepared_artifact() -> PreparedImageArtifact:
    return PreparedImageArtifact(
        entity_id(40),
        entity_id(20),
        entity_id(30),
        entity_id(41),
        PREPARED_JPEG_PIPELINE_ID,
        1,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        1,
        PreparedMediaType.JPEG,
        ColorSpace.SRGB,
        8,
        8,
        64,
        DomainDigest("c" * 64),
        95,
        100,
        STAMP,
        actor(),
    )


prepared_artifact = valid_prepared_artifact


class Provider:
    def get_database_key(self) -> bytes:
        return b"k" * 32


def open_sqlite(path: Path, provider: object | None = None) -> sqlite3.Connection:
    del provider
    c = sqlite3.connect(path, isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def assert_foreign_keys(c: sqlite3.Connection) -> None:
    assert c.execute("PRAGMA foreign_keys").fetchone() == (1,)


@dataclass(frozen=True, slots=True)
class PopulatedV6Fixture:
    path: Path
    batch: UploadBatch
    persisted_batch: UploadBatch
    original: StoredArtifactRecord
    source: SourceFile
    historical_audit: AuditEvent
    quality_audit: AuditEvent
    geometry_audit: AuditEvent
    quality_metrics: tuple[ImageQualityMetric, ...]
    quality_issues: tuple[ImageQualityIssue, ...]
    assessment: ImageQualityAssessment
    recipe: ImageGeometryRecipe


def build_populated_schema_v6(path: Path, monkeypatch: Any) -> PopulatedV6Fixture:
    c = open_sqlite(path)
    for m in MIGRATIONS[:6]:
        database._apply_one_migration(c, m)
    c.close()
    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    monkeypatch.setattr(database, "CURRENT_SCHEMA_VERSION", 6)
    batch = valid_upload_batch()
    source = valid_source_file()
    original = valid_original_stored_artifact()
    assessment = valid_quality_assessment()
    recipe = valid_geometry_recipe()
    audits = (valid_audit_event(), valid_quality_audit_event(), valid_geometry_audit_event())
    persisted_batch = batch.append_source_file_id(source.id)
    with SqlCipherUnitOfWork(path, Provider()) as u:
        u.upload_batches.add(batch)
        u.stored_artifacts.add(original)
        u.source_files.add(source)
        u.upload_batches.update(persisted_batch)
        u.image_quality_assessments.add(assessment)
        columns = geometry_serialization.image_geometry_recipe_columns(recipe)
        payload = json.loads(geometry_serialization.image_geometry_recipe_to_json(recipe))
        payload.pop("region_id")
        u._connection().execute(
            "INSERT INTO image_geometry_recipes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                *(columns[0], columns[1], *columns[3:]),
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            ),
        )
        for a in audits:
            u.audit_events.add(a)
        u.commit()
    return PopulatedV6Fixture(
        path,
        batch,
        persisted_batch,
        original,
        source,
        audits[0],
        audits[1],
        audits[2],
        assessment.metrics,
        assessment.issues,
        assessment,
        recipe,
    )


class CommitFailureUow:
    def __init__(self, delegated: Any):
        self.delegated = delegated
        self.entered = None
        self.commit_attempts = 0

    def __enter__(self):
        self.entered = self.delegated.__enter__()
        return self

    def __exit__(self, *args):
        return self.delegated.__exit__(*args)

    def commit(self):
        self.commit_attempts += 1
        raise RuntimeError("SYNTHETIC_COMMIT_FAILURE")

    def __getattr__(self, name: str) -> Any:
        return getattr(self.entered if self.entered is not None else self.delegated, name)


class RecordingCommitUow:
    def __init__(self, delegated: Any):
        self.delegated = delegated
        self.entered = None
        self.commit_calls = 0

    def __enter__(self):
        self.entered = self.delegated.__enter__()
        return self

    def __exit__(self, *args):
        return self.delegated.__exit__(*args)

    def commit(self):
        self.commit_calls += 1
        return self.entered.commit()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.entered if self.entered is not None else self.delegated, name)


@dataclass(slots=True)
class CallRecorder:
    calls: list[str]

    def record(self, v: str) -> None:
        self.calls.append(v)
