from pathlib import Path

import pytest

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.entities.imports import SourceFile, UploadBatch
from document_intake.domain.image_geometry import ImageGeometryRecipe
from document_intake.domain.image_quality import (
    ImageQualityAssessment,
    ImageQualityIssue,
    ImageQualityMetric,
)
from document_intake.domain.prepared_jpeg import PreparedImageArtifact
from document_intake.persistence import database
from document_intake.persistence.database import SqlCipherUnitOfWork
from tests.support import pr011


def test_typed_builders_are_deterministic_and_coherent():
    values = [
        pr011.valid_upload_batch(),
        pr011.valid_original_stored_artifact(),
        pr011.valid_source_file(),
        pr011.valid_audit_event(),
        pr011.valid_quality_audit_event(),
        pr011.valid_quality_issue(),
        pr011.valid_quality_assessment(),
        pr011.valid_geometry_audit_event(),
        pr011.valid_geometry_recipe(),
        pr011.valid_prepared_stored_artifact(),
        pr011.valid_prepared_artifact(),
    ]
    types = (
        UploadBatch,
        StoredArtifactRecord,
        SourceFile,
        AuditEvent,
        AuditEvent,
        ImageQualityIssue,
        ImageQualityAssessment,
        AuditEvent,
        ImageGeometryRecipe,
        StoredArtifactRecord,
        PreparedImageArtifact,
    )
    assert all(type(v) is t for v, t in zip(values, types, strict=True))
    assert not any(isinstance(v, dict) for v in values)
    metrics = pr011.valid_quality_metrics()
    assert len(metrics) == 7 and all(type(m) is ImageQualityMetric for m in metrics)
    assessment = pr011.valid_quality_assessment()
    assert assessment.status is pr011.QualityAssessmentStatus.REVIEW_REQUIRED
    assert assessment.issues == (pr011.valid_quality_issue(),)
    assert pr011._policy().minimum_short_side_pixels == 25
    assert metrics[0].numeric_value == 24 and metrics[1].numeric_value == 32
    assert (
        values[6].source_file_id
        == values[2].id
        == values[8].source_file_id
        == values[10].source_file_id
    )
    assert values[10].geometry_recipe_version_id == values[8].recipe_version_id
    assert values[9].artifact_id == values[10].stored_artifact_id
    assert pr011.entity_id(1) == pr011.entity_id(1)
    assert pr011.STAMP.utcoffset().total_seconds() == 0


def assert_populated_v6_fixture(u: SqlCipherUnitOfWork, fixture: pr011.PopulatedV6Fixture) -> None:
    c = u._connection()
    assert c.execute("PRAGMA user_version").fetchone() == (6,)
    pr011.assert_foreign_keys(c)
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    assert c.execute(
        "SELECT count(*) FROM image_quality_metrics WHERE assessment_id=?",
        (str(fixture.assessment.id),),
    ).fetchone() == (7,)
    assert c.execute(
        "SELECT count(*) FROM image_quality_issues WHERE assessment_id=?",
        (str(fixture.assessment.id),),
    ).fetchone() == (1,)
    assert u.upload_batches.get(fixture.batch.id) == fixture.persisted_batch
    assert fixture.persisted_batch.source_file_ids == (fixture.source.id,)
    assert u.source_files.get(fixture.source.id) == fixture.source
    assert u.stored_artifacts.get(fixture.original.artifact_id) == fixture.original
    assert u.audit_events.get(fixture.historical_audit.event_id) == fixture.historical_audit
    assert u.audit_events.get(fixture.quality_audit.event_id) == fixture.quality_audit
    assert u.audit_events.get(fixture.geometry_audit.event_id) == fixture.geometry_audit
    assessment = u.image_quality_assessments.get(fixture.assessment.id)
    assert assessment == fixture.assessment
    assert assessment.metrics == fixture.quality_metrics
    assert assessment.issues == fixture.quality_issues
    assert assessment.status is pr011.QualityAssessmentStatus.REVIEW_REQUIRED
    assert assessment.issues == (
        pr011.ImageQualityIssue(
            pr011.QualityIssueCode.LOW_RESOLUTION, pr011.QualityIssueSeverity.WARNING
        ),
    )
    assert u.image_geometry_recipes.get(fixture.recipe.recipe_version_id) == fixture.recipe


def test_file_backed_populated_v6_survives_reopen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "v6.db"
    fixture = pr011.build_populated_schema_v6(path, monkeypatch)
    with SqlCipherUnitOfWork(path, pr011.Provider()) as first:
        assert_populated_v6_fixture(first, fixture)
    with SqlCipherUnitOfWork(path, pr011.Provider()) as reopened:
        assert_populated_v6_fixture(reopened, fixture)


def test_commit_wrapper_never_delegates_commit_and_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "rollback.db"
    source = __import__("sqlite3").connect(path, isolation_level=None)
    source.execute("PRAGMA foreign_keys=ON")
    for m in database.MIGRATIONS:
        database._apply_one_migration(source, m)
    source.close()
    monkeypatch.setattr(database, "_open_connection", pr011.open_sqlite)
    recording = pr011.RecordingCommitUow(SqlCipherUnitOfWork(path, pr011.Provider()))
    wrapper = pr011.CommitFailureUow(recording)
    with pytest.raises(RuntimeError, match="SYNTHETIC_COMMIT_FAILURE"), wrapper as u:
        u.upload_batches.add(pr011.valid_upload_batch())
        u.commit()
    assert wrapper.commit_attempts == 1
    assert recording.commit_calls == 0
    with SqlCipherUnitOfWork(path, pr011.Provider()) as u:
        assert u.upload_batches.get(pr011.valid_upload_batch().id) is None


def test_call_recorder_preserves_order():
    r = pr011.CallRecorder([])
    r.record("first")
    r.record("second")
    assert r.calls == ["first", "second"]
