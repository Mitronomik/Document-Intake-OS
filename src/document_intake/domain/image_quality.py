"""Immutable PR-009 image quality domain contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from document_intake.domain.enums import (
    QualityAssessmentStatus,
    QualityIssueCode,
    QualityIssueSeverity,
    QualityMetricCode,
    QualityMetricUnit,
)
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import EntityId

_POLICY_RE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
METRIC_ORDER = tuple(QualityMetricCode)
ISSUE_ORDER = tuple(QualityIssueCode)
_METRIC_META = {
    QualityMetricCode.SHORT_SIDE_PIXELS: ("RESOLUTION_V1", QualityMetricUnit.PIXELS),
    QualityMetricCode.LONG_SIDE_PIXELS: ("RESOLUTION_V1", QualityMetricUnit.PIXELS),
    QualityMetricCode.LAPLACIAN_VARIANCE: ("BLUR_LAPLACIAN_V1", QualityMetricUnit.VARIANCE),
    QualityMetricCode.LUMINANCE_STANDARD_DEVIATION: (
        "CONTRAST_STDDEV_V1",
        QualityMetricUnit.LUMA_LEVEL,
    ),
    QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION: (
        "GLARE_CLIPPED_FRACTION_V1",
        QualityMetricUnit.FRACTION,
    ),
    QualityMetricCode.SHADOW_CLIPPED_FRACTION: (
        "EXPOSURE_CLIPPED_FRACTION_V1",
        QualityMetricUnit.FRACTION,
    ),
    QualityMetricCode.BRIGHT_CLIPPED_FRACTION: (
        "EXPOSURE_CLIPPED_FRACTION_V1",
        QualityMetricUnit.FRACTION,
    ),
}


def _decimal(v: Decimal, name: str) -> Decimal:
    if type(v) is not Decimal or v.is_nan() or v.is_infinite():
        raise InvalidValueError(f"{name}: finite_decimal_required")
    return v


def _has_scale(value: Decimal, places: int) -> bool:
    return value.as_tuple().exponent == -places


def _utc(dt: datetime) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise InvalidValueError("image_quality_assessment.assessed_at: timezone_required")
    return dt.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class QualityPolicyVersion:
    policy_id: str
    version: int

    def __post_init__(self) -> None:
        if type(self.policy_id) is not str or not _POLICY_RE.fullmatch(self.policy_id):
            raise InvalidValueError("quality_policy_version.policy_id: invalid_format")
        if type(self.version) is not int or self.version < 1:
            raise InvalidValueError("quality_policy_version.version: invalid_value")


@dataclass(frozen=True, slots=True)
class ImageQualityMetric:
    metric_code: QualityMetricCode
    algorithm_id: str
    algorithm_version: int
    numeric_value: Decimal
    unit: QualityMetricUnit

    def __post_init__(self) -> None:
        if not isinstance(self.metric_code, QualityMetricCode):
            raise InvalidValueError("image_quality_metric.metric_code: invalid_type")
        if type(self.algorithm_id) is not str:
            raise InvalidValueError("image_quality_metric.algorithm_id: invalid_type")
        if type(self.algorithm_version) is not int:
            raise InvalidValueError("image_quality_metric.algorithm_version: invalid_type")
        expected_alg, expected_unit = _METRIC_META[self.metric_code]
        if (
            self.algorithm_id != expected_alg
            or self.algorithm_version != 1
            or self.unit is not expected_unit
        ):
            raise InvalidValueError("image_quality_metric: invalid_mapping")
        value = _decimal(self.numeric_value, "image_quality_metric.numeric_value")
        if value < 0:
            raise InvalidValueError("image_quality_metric.numeric_value: negative")
        if self.unit is QualityMetricUnit.PIXELS:
            if value != value.to_integral_value() or value.as_tuple().exponent != 0 or value < 1:
                raise InvalidValueError("image_quality_metric.numeric_value: invalid_pixels")
        elif self.unit in {QualityMetricUnit.VARIANCE, QualityMetricUnit.LUMA_LEVEL}:
            if not _has_scale(value, 6):
                raise InvalidValueError("image_quality_metric.numeric_value: invalid_scale")
        elif self.unit is QualityMetricUnit.FRACTION and (
            not _has_scale(value, 8) or not Decimal("0") <= value <= Decimal("1")
        ):
            raise InvalidValueError("image_quality_metric.numeric_value: invalid_fraction")


@dataclass(frozen=True, slots=True)
class ImageQualitySeverityRule:
    issue_code: QualityIssueCode
    severity: QualityIssueSeverity

    def __post_init__(self) -> None:
        if not isinstance(self.issue_code, QualityIssueCode) or not isinstance(
            self.severity, QualityIssueSeverity
        ):
            raise InvalidValueError("image_quality_severity_rule: invalid_type")


@dataclass(frozen=True, slots=True)
class ImageQualityIssue:
    issue_code: QualityIssueCode
    severity: QualityIssueSeverity

    def __post_init__(self) -> None:
        if not isinstance(self.issue_code, QualityIssueCode) or not isinstance(
            self.severity, QualityIssueSeverity
        ):
            raise InvalidValueError("image_quality_issue: invalid_type")


@dataclass(frozen=True, slots=True)
class ImageQualityPolicy:
    version: QualityPolicyVersion
    minimum_short_side_pixels: int
    minimum_long_side_pixels: int
    blur_minimum_laplacian_variance: Decimal
    contrast_minimum_luminance_stddev: Decimal
    glare_highlight_cutoff: int
    glare_maximum_fraction: Decimal
    exposure_shadow_cutoff: int
    exposure_maximum_shadow_fraction: Decimal
    exposure_bright_cutoff: int
    exposure_maximum_bright_fraction: Decimal
    severity_rules: tuple[ImageQualitySeverityRule, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.version, QualityPolicyVersion):
            raise InvalidValueError("image_quality_policy.version: invalid_type")
        if (
            type(self.minimum_short_side_pixels) is not int
            or type(self.minimum_long_side_pixels) is not int
            or self.minimum_short_side_pixels < 1
            or self.minimum_long_side_pixels < self.minimum_short_side_pixels
        ):
            raise InvalidValueError("image_quality_policy.dimensions: invalid_value")
        for name in (
            "blur_minimum_laplacian_variance",
            "contrast_minimum_luminance_stddev",
            "glare_maximum_fraction",
            "exposure_maximum_shadow_fraction",
            "exposure_maximum_bright_fraction",
        ):
            _decimal(getattr(self, name), f"image_quality_policy.{name}")
        if self.blur_minimum_laplacian_variance < 0 or self.contrast_minimum_luminance_stddev < 0:
            raise InvalidValueError("image_quality_policy.threshold: negative")
        if not all(
            Decimal("0") <= getattr(self, n) <= Decimal("1")
            for n in (
                "glare_maximum_fraction",
                "exposure_maximum_shadow_fraction",
                "exposure_maximum_bright_fraction",
            )
        ):
            raise InvalidValueError("image_quality_policy.fraction: out_of_range")
        for n in ("glare_highlight_cutoff", "exposure_shadow_cutoff", "exposure_bright_cutoff"):
            v = getattr(self, n)
            if type(v) is not int or not 0 <= v <= 255:
                raise InvalidValueError("image_quality_policy.cutoff: invalid_value")
        if self.exposure_shadow_cutoff >= self.exposure_bright_cutoff:
            raise InvalidValueError("image_quality_policy.exposure_cutoffs: invalid_order")
        if type(self.severity_rules) is not tuple:
            raise InvalidValueError("image_quality_policy.severity_rules: invalid_type")
        if any(not isinstance(r, ImageQualitySeverityRule) for r in self.severity_rules):
            raise InvalidValueError("image_quality_policy.severity_rules: invalid_item_type")
        if tuple(r.issue_code for r in self.severity_rules) != ISSUE_ORDER:
            raise InvalidValueError("image_quality_policy.severity_rules: invalid_order")


def derive_quality_issues_and_status(
    metrics: tuple[ImageQualityMetric, ...],
    policy: ImageQualityPolicy,
) -> tuple[tuple[ImageQualityIssue, ...], QualityAssessmentStatus]:
    if type(metrics) is not tuple:
        raise InvalidValueError("image_quality_metrics: invalid_type")
    if any(not isinstance(metric, ImageQualityMetric) for metric in metrics):
        raise InvalidValueError("image_quality_metrics: invalid_item_type")
    if tuple(metric.metric_code for metric in metrics) != METRIC_ORDER:
        raise InvalidValueError("image_quality_metrics: invalid_order")
    if len({metric.metric_code for metric in metrics}) != len(metrics) or len(metrics) != 7:
        raise InvalidValueError("image_quality_metrics: invalid_count")
    if not isinstance(policy, ImageQualityPolicy):
        raise InvalidValueError("image_quality_policy: invalid_type")
    metric_values = {metric.metric_code: metric.numeric_value for metric in metrics}
    severities = {rule.issue_code: rule.severity for rule in policy.severity_rules}
    checks = (
        (
            QualityIssueCode.LOW_RESOLUTION,
            metric_values[QualityMetricCode.SHORT_SIDE_PIXELS]
            < Decimal(policy.minimum_short_side_pixels)
            or metric_values[QualityMetricCode.LONG_SIDE_PIXELS]
            < Decimal(policy.minimum_long_side_pixels),
        ),
        (
            QualityIssueCode.BLUR_DETECTED,
            metric_values[QualityMetricCode.LAPLACIAN_VARIANCE]
            < policy.blur_minimum_laplacian_variance,
        ),
        (
            QualityIssueCode.LOW_CONTRAST,
            metric_values[QualityMetricCode.LUMINANCE_STANDARD_DEVIATION]
            < policy.contrast_minimum_luminance_stddev,
        ),
        (
            QualityIssueCode.GLARE_DETECTED,
            metric_values[QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION]
            > policy.glare_maximum_fraction,
        ),
        (
            QualityIssueCode.UNDEREXPOSED,
            metric_values[QualityMetricCode.SHADOW_CLIPPED_FRACTION]
            > policy.exposure_maximum_shadow_fraction,
        ),
        (
            QualityIssueCode.OVEREXPOSED,
            metric_values[QualityMetricCode.BRIGHT_CLIPPED_FRACTION]
            > policy.exposure_maximum_bright_fraction,
        ),
    )
    issues = tuple(
        ImageQualityIssue(code, severities[code]) for code, is_present in checks if is_present
    )
    status = (
        QualityAssessmentStatus.GOOD
        if not issues
        else (
            QualityAssessmentStatus.RETAKE_REQUIRED
            if any(issue.severity is QualityIssueSeverity.BLOCKING for issue in issues)
            else QualityAssessmentStatus.REVIEW_REQUIRED
        )
    )
    return issues, status


@dataclass(frozen=True, slots=True)
class ImageQualityAssessment:
    id: EntityId
    source_file_id: EntityId
    assessed_at: datetime
    policy: ImageQualityPolicy
    status: QualityAssessmentStatus
    encoded_width: int
    encoded_height: int
    exif_orientation: int | None
    effective_width: int
    effective_height: int
    metrics: tuple[ImageQualityMetric, ...]
    issues: tuple[ImageQualityIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, EntityId) or not isinstance(self.source_file_id, EntityId):
            raise InvalidValueError("image_quality_assessment.id: invalid_type")
        object.__setattr__(self, "assessed_at", _utc(self.assessed_at))
        if not isinstance(self.policy, ImageQualityPolicy):
            raise InvalidValueError("image_quality_assessment.policy: invalid_type")
        if not isinstance(self.status, QualityAssessmentStatus):
            raise InvalidValueError("image_quality_assessment.status: invalid_type")
        if any(
            type(v) is not int or v < 1
            for v in (
                self.encoded_width,
                self.encoded_height,
                self.effective_width,
                self.effective_height,
            )
        ):
            raise InvalidValueError("image_quality_assessment.dimensions: invalid_value")
        if self.exif_orientation is not None and (
            type(self.exif_orientation) is not int or not 1 <= self.exif_orientation <= 8
        ):
            raise InvalidValueError("image_quality_assessment.exif_orientation: invalid_value")
        if self.exif_orientation in {5, 6, 7, 8} and (
            self.effective_width,
            self.effective_height,
        ) != (self.encoded_height, self.encoded_width):
            raise InvalidValueError("image_quality_assessment.effective_dimensions: invalid_swap")
        if self.exif_orientation not in {5, 6, 7, 8} and (
            self.effective_width,
            self.effective_height,
        ) != (self.encoded_width, self.encoded_height):
            raise InvalidValueError(
                "image_quality_assessment.effective_dimensions: invalid_identity"
            )
        if type(self.metrics) is not tuple:
            raise InvalidValueError("image_quality_assessment.metrics: invalid_type")
        if any(not isinstance(metric, ImageQualityMetric) for metric in self.metrics):
            raise InvalidValueError("image_quality_assessment.metrics: invalid_item_type")
        if tuple(m.metric_code for m in self.metrics) != METRIC_ORDER:
            raise InvalidValueError("image_quality_assessment.metrics: invalid_order")
        if (
            len({m.metric_code for m in self.metrics}) != len(self.metrics)
            or len(self.metrics) != 7
        ):
            raise InvalidValueError("image_quality_assessment.metrics: invalid_count")
        if type(self.issues) is not tuple:
            raise InvalidValueError("image_quality_assessment.issues: invalid_type")
        if any(not isinstance(issue, ImageQualityIssue) for issue in self.issues):
            raise InvalidValueError("image_quality_assessment.issues: invalid_item_type")
        if len({i.issue_code for i in self.issues}) != len(self.issues):
            raise InvalidValueError("image_quality_assessment.issues: duplicate")
        if tuple(i.issue_code for i in self.issues) != tuple(
            c for c in ISSUE_ORDER if c in {i.issue_code for i in self.issues}
        ):
            raise InvalidValueError("image_quality_assessment.issues: invalid_order")
        metric_values = {metric.metric_code: metric.numeric_value for metric in self.metrics}
        if metric_values[QualityMetricCode.SHORT_SIDE_PIXELS] != Decimal(
            min(self.effective_width, self.effective_height)
        ) or metric_values[QualityMetricCode.LONG_SIDE_PIXELS] != Decimal(
            max(self.effective_width, self.effective_height)
        ):
            raise InvalidValueError("image_quality_assessment.metrics: dimension_mismatch")
        expected_issues, expected_status = derive_quality_issues_and_status(
            self.metrics, self.policy
        )
        if self.issues != expected_issues:
            raise InvalidValueError("image_quality_assessment.issues: mismatch")
        if self.status is not expected_status:
            raise InvalidValueError("image_quality_assessment.status: mismatch")
