"""PR-009 image quality DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_quality import ImageQualityAssessment, ImageQualityPolicy
from document_intake.domain.value_objects import ActorRef, EntityId


@dataclass(frozen=True, slots=True)
class AssessSourceFileQualityCommand:
    source_file_id: EntityId
    assessment_id: EntityId
    audit_event_id: EntityId
    assessed_at: datetime
    actor: ActorRef
    policy: ImageQualityPolicy
    correlation_id: EntityId

    def __post_init__(self) -> None:
        for n in ("source_file_id", "assessment_id", "audit_event_id", "correlation_id"):
            if not isinstance(getattr(self, n), EntityId):
                raise InvalidValueError(f"assess_source_file_quality_command.{n}: invalid_type")
        if self.assessment_id == self.audit_event_id:
            raise InvalidValueError("assess_source_file_quality_command.ids: not_distinct")
        if (
            not isinstance(self.assessed_at, datetime)
            or self.assessed_at.tzinfo is None
            or self.assessed_at.utcoffset() is None
        ):
            raise InvalidValueError(
                "assess_source_file_quality_command.assessed_at: timezone_required"
            )
        object.__setattr__(self, "assessed_at", self.assessed_at.astimezone(UTC))
        if not isinstance(self.actor, ActorRef):
            raise InvalidValueError("assess_source_file_quality_command.actor: invalid_type")
        if not isinstance(self.policy, ImageQualityPolicy):
            raise InvalidValueError("assess_source_file_quality_command.policy: invalid_type")


@dataclass(frozen=True, slots=True)
class AssessSourceFileQualityResult:
    assessment: ImageQualityAssessment

    def __post_init__(self) -> None:
        if not isinstance(self.assessment, ImageQualityAssessment):
            raise InvalidValueError("assess_source_file_quality_result.assessment: invalid_type")
