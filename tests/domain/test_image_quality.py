from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from document_intake.domain.enums import (
    QualityAssessmentStatus,
    QualityIssueCode,
    QualityIssueSeverity,
    QualityMetricCode,
    QualityMetricUnit,
)
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_quality import (
    ImageQualityAssessment,
    ImageQualityMetric,
    ImageQualityPolicy,
    ImageQualitySeverityRule,
    QualityPolicyVersion,
    derive_quality_issues_and_status,
)
from document_intake.domain.value_objects import EntityId


def eid(i: int) -> EntityId:
    return EntityId(UUID(int=i))


def rules(sev=QualityIssueSeverity.WARNING):
    return tuple(ImageQualitySeverityRule(c, sev) for c in QualityIssueCode)


def policy(**kw) -> ImageQualityPolicy:
    base = dict(
        version=QualityPolicyVersion("TEST_PR009", 1),
        minimum_short_side_pixels=2,
        minimum_long_side_pixels=4,
        blur_minimum_laplacian_variance=Decimal("1"),
        contrast_minimum_luminance_stddev=Decimal("1"),
        glare_highlight_cutoff=200,
        glare_maximum_fraction=Decimal("0.5"),
        exposure_shadow_cutoff=10,
        exposure_maximum_shadow_fraction=Decimal("0.5"),
        exposure_bright_cutoff=240,
        exposure_maximum_bright_fraction=Decimal("0.5"),
        severity_rules=rules(),
    )
    base.update(kw)
    return ImageQualityPolicy(**base)


def metric(code, val):
    alg = {
        QualityMetricCode.SHORT_SIDE_PIXELS: "RESOLUTION_V1",
        QualityMetricCode.LONG_SIDE_PIXELS: "RESOLUTION_V1",
        QualityMetricCode.LAPLACIAN_VARIANCE: "BLUR_LAPLACIAN_V1",
        QualityMetricCode.LUMINANCE_STANDARD_DEVIATION: "CONTRAST_STDDEV_V1",
        QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION: "GLARE_CLIPPED_FRACTION_V1",
        QualityMetricCode.SHADOW_CLIPPED_FRACTION: "EXPOSURE_CLIPPED_FRACTION_V1",
        QualityMetricCode.BRIGHT_CLIPPED_FRACTION: "EXPOSURE_CLIPPED_FRACTION_V1",
    }[code]
    unit = {
        QualityMetricCode.SHORT_SIDE_PIXELS: QualityMetricUnit.PIXELS,
        QualityMetricCode.LONG_SIDE_PIXELS: QualityMetricUnit.PIXELS,
        QualityMetricCode.LAPLACIAN_VARIANCE: QualityMetricUnit.VARIANCE,
        QualityMetricCode.LUMINANCE_STANDARD_DEVIATION: QualityMetricUnit.LUMA_LEVEL,
        QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION: QualityMetricUnit.FRACTION,
        QualityMetricCode.SHADOW_CLIPPED_FRACTION: QualityMetricUnit.FRACTION,
        QualityMetricCode.BRIGHT_CLIPPED_FRACTION: QualityMetricUnit.FRACTION,
    }[code]
    return ImageQualityMetric(code, alg, 1, Decimal(val), unit)


def good_metrics():
    return (
        metric(QualityMetricCode.SHORT_SIDE_PIXELS, "2"),
        metric(QualityMetricCode.LONG_SIDE_PIXELS, "4"),
        metric(QualityMetricCode.LAPLACIAN_VARIANCE, "1.000000"),
        metric(QualityMetricCode.LUMINANCE_STANDARD_DEVIATION, "1.000000"),
        metric(QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION, "0.50000000"),
        metric(QualityMetricCode.SHADOW_CLIPPED_FRACTION, "0.50000000"),
        metric(QualityMetricCode.BRIGHT_CLIPPED_FRACTION, "0.50000000"),
    )


def test_enums_and_metric_scales() -> None:
    assert QualityAssessmentStatus.GOOD.value == "GOOD"
    with pytest.raises(InvalidValueError):
        metric(QualityMetricCode.LAPLACIAN_VARIANCE, "12")
    with pytest.raises(InvalidValueError):
        metric(QualityMetricCode.SHORT_SIDE_PIXELS, "12.000000")
    with pytest.raises(InvalidValueError):
        metric(QualityMetricCode.BRIGHT_CLIPPED_FRACTION, "0.5")
    with pytest.raises(InvalidValueError):
        ImageQualityMetric(
            QualityMetricCode.SHORT_SIDE_PIXELS, "BAD", 1, Decimal("12"), QualityMetricUnit.PIXELS
        )
    with pytest.raises(InvalidValueError):
        ImageQualityMetric(
            QualityMetricCode.SHORT_SIDE_PIXELS,
            "RESOLUTION_V1",
            True,
            Decimal("12"),
            QualityMetricUnit.PIXELS,
        )


def test_policy_exact_tuple_and_decimal_validation() -> None:
    with pytest.raises(InvalidValueError):
        QualityPolicyVersion("bad", 1)
    with pytest.raises(InvalidValueError):
        policy(severity_rules=list(rules()))
    with pytest.raises(InvalidValueError):
        policy(severity_rules=rules()[:-1])
    with pytest.raises(InvalidValueError):
        policy(blur_minimum_laplacian_variance=Decimal("NaN"))
    with pytest.raises(InvalidValueError):
        policy(exposure_shadow_cutoff=250, exposure_bright_cutoff=100)


def test_derive_and_assessment_cross_field_validation() -> None:
    p = policy()
    metrics = good_metrics()
    issues, status = derive_quality_issues_and_status(metrics, p)
    assert issues == ()
    assert status is QualityAssessmentStatus.GOOD
    ImageQualityAssessment(
        eid(1),
        eid(2),
        datetime(2026, 7, 21, tzinfo=UTC),
        p,
        status,
        2,
        4,
        None,
        2,
        4,
        metrics,
        issues,
    )
    bad = (metric(QualityMetricCode.SHORT_SIDE_PIXELS, "1"), *metrics[1:])
    issues, status = derive_quality_issues_and_status(bad, p)
    assert issues[0].issue_code is QualityIssueCode.LOW_RESOLUTION
    with pytest.raises(InvalidValueError):
        ImageQualityAssessment(
            eid(1),
            eid(2),
            datetime(2026, 7, 21, tzinfo=UTC),
            p,
            QualityAssessmentStatus.GOOD,
            2,
            4,
            None,
            2,
            4,
            bad,
            (),
        )
    with pytest.raises(InvalidValueError):
        ImageQualityAssessment(
            eid(1),
            eid(2),
            datetime(2026, 7, 21, tzinfo=UTC),
            p,
            QualityAssessmentStatus.GOOD,
            2,
            4,
            None,
            2,
            4,
            list(metrics),
            (),
        )
    assert "path" not in repr(p).lower()
