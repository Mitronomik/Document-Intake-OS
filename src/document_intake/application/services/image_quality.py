"""PR-009 image quality application service."""

from __future__ import annotations

from typing import NoReturn

from document_intake.application.dto.image_quality import (
    AssessSourceFileQualityCommand,
    AssessSourceFileQualityResult,
)
from document_intake.application.ports.media import QualityAnalysisDecoderPort
from document_intake.application.ports.persistence import UnitOfWorkFactory
from document_intake.application.ports.storage import StoragePort
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import (
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    QualityAssessmentErrorCode,
)
from document_intake.domain.image_quality import ImageQualityAssessment
from document_intake.domain.value_objects import AuditReasonCode, AuditValueSummary
from document_intake.image_pipeline.quality_assessor import (
    calculate_quality_metrics,
    evaluate_quality_policy,
)
from document_intake.persistence.serialization import image_quality_policy_to_json


class QualityAssessmentError(Exception):
    def __init__(self, code: QualityAssessmentErrorCode) -> None:
        if not isinstance(code, QualityAssessmentErrorCode):
            raise TypeError("quality_assessment_error.code: invalid_type")
        self.code = code
        super().__init__(code.value)

    def __repr__(self) -> str:
        return f"QualityAssessmentError(code={self.code.value})"


def _raise(code: QualityAssessmentErrorCode) -> NoReturn:
    raise QualityAssessmentError(code) from None


def assess_source_file_quality(
    command: AssessSourceFileQualityCommand,
    *,
    decoder: QualityAnalysisDecoderPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> AssessSourceFileQualityResult:
    try:
        image_quality_policy_to_json(command.policy)
    except Exception:
        _raise(QualityAssessmentErrorCode.QUALITY_POLICY_INVALID)
    try:
        cm = unit_of_work_factory.unit_of_work()
        with cm as uow:
            try:
                source = uow.source_files.get(command.source_file_id)
            except Exception:
                _raise(QualityAssessmentErrorCode.PERSISTENCE_FAILED)
            if source is None:
                _raise(QualityAssessmentErrorCode.SOURCE_FILE_NOT_FOUND)
            assert source is not None
            try:
                stored = uow.stored_artifacts.get(source.original_artifact_id)
            except Exception:
                _raise(QualityAssessmentErrorCode.PERSISTENCE_FAILED)
            if stored is None:
                _raise(QualityAssessmentErrorCode.ARTIFACT_NOT_FOUND)
            assert stored is not None
            try:
                content = storage.read_bytes(expected=stored)
            except Exception:
                _raise(QualityAssessmentErrorCode.ARTIFACT_INTEGRITY_FAILED)
            try:
                media = decoder.decode_for_quality(content=content)
            except Exception:
                _raise(QualityAssessmentErrorCode.DECODE_FAILED)
            try:
                metrics = calculate_quality_metrics(media, policy=command.policy)
                status, issues = evaluate_quality_policy(metrics, command.policy)
                assessment = ImageQualityAssessment(
                    command.assessment_id,
                    command.source_file_id,
                    command.assessed_at,
                    command.policy,
                    status,
                    media.encoded_width,
                    media.encoded_height,
                    media.exif_orientation,
                    media.effective_width,
                    media.effective_height,
                    metrics,
                    issues,
                )
            except Exception:
                _raise(QualityAssessmentErrorCode.QUALITY_ASSESSMENT_FAILED)
            try:
                uow.image_quality_assessments.add(assessment)
                event = AuditEvent(
                    event_id=command.audit_event_id,
                    occurred_at=command.assessed_at,
                    actor=command.actor,
                    action_code=AuditAction.IMAGE_QUALITY_ASSESSED,
                    subject_type=AuditSubjectType.IMAGE_QUALITY_ASSESSMENT,
                    subject_id=command.assessment_id,
                    field_key=None,
                    before=AuditValueSummary(AuditValueClassification.ABSENT, None, False),
                    after=AuditValueSummary(
                        AuditValueClassification.NON_SENSITIVE, "QUALITY_ASSESSMENT", True
                    ),
                    reason_code=AuditReasonCode("IMAGE_QUALITY_ASSESSMENT"),
                    correlation_id=command.correlation_id,
                )
                uow.audit_events.add(event)
                uow.commit()
            except QualityAssessmentError:
                raise
            except Exception:
                _raise(QualityAssessmentErrorCode.PERSISTENCE_FAILED)
        return AssessSourceFileQualityResult(assessment)
    except QualityAssessmentError:
        raise
    except Exception:
        _raise(QualityAssessmentErrorCode.PERSISTENCE_FAILED)
