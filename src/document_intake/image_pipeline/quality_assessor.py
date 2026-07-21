"""Deterministic PR-009 whole-frame quality metrics."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext

from document_intake.application.ports.media import DecodedQualityMedia
from document_intake.domain.enums import (
    QualityAssessmentStatus,
    QualityIssueCode,
    QualityIssueSeverity,
    QualityMetricCode,
    QualityMetricUnit,
)
from document_intake.domain.image_quality import (
    ImageQualityIssue,
    ImageQualityMetric,
    ImageQualityPolicy,
)

Q6 = Decimal("0.000001")
Q8 = Decimal("0.00000001")


def _q(v: Decimal, q: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        return v.quantize(q)


def _frac(n: int, d: int) -> Decimal:
    return _q(Decimal(n) / Decimal(d), Q8)


def calculate_quality_metrics(media: DecodedQualityMedia) -> tuple[ImageQualityMetric, ...]:
    w = media.grayscale_width
    h = media.grayscale_height
    px = media.grayscale_pixels
    total = w * h
    vals = list(px)
    short = Decimal(min(media.effective_width, media.effective_height))
    long = Decimal(max(media.effective_width, media.effective_height))
    laps = []
    if w >= 3 and h >= 3:
        for y in range(1, h - 1):
            o = y * w
            for x in range(1, w - 1):
                laps.append(
                    px[o - w + x] + px[o - 1 + x] + px[o + 1 + x] + px[o + w + x] - 4 * px[o + x]
                )
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        if laps:
            s = sum(laps)
            ss = sum(v * v for v in laps)
            n = Decimal(len(laps))
            mean = Decimal(s) / n
            var = Decimal(ss) / n - mean * mean
        else:
            var = Decimal(0)
        s = sum(vals)
        ss = sum(v * v for v in vals)
        n = Decimal(total)
        mean = Decimal(s) / n
        std = (Decimal(ss) / n - mean * mean).sqrt()
    return (
        ImageQualityMetric(
            QualityMetricCode.SHORT_SIDE_PIXELS, "RESOLUTION_V1", 1, short, QualityMetricUnit.PIXELS
        ),
        ImageQualityMetric(
            QualityMetricCode.LONG_SIDE_PIXELS, "RESOLUTION_V1", 1, long, QualityMetricUnit.PIXELS
        ),
        ImageQualityMetric(
            QualityMetricCode.LAPLACIAN_VARIANCE,
            "BLUR_LAPLACIAN_V1",
            1,
            _q(var, Q6),
            QualityMetricUnit.VARIANCE,
        ),
        ImageQualityMetric(
            QualityMetricCode.LUMINANCE_STANDARD_DEVIATION,
            "CONTRAST_STDDEV_V1",
            1,
            _q(std, Q6),
            QualityMetricUnit.LUMA_LEVEL,
        ),
        ImageQualityMetric(
            QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION,
            "GLARE_CLIPPED_FRACTION_V1",
            1,
            _frac(sum(v >= 255 for v in vals), total),
            QualityMetricUnit.FRACTION,
        ),
        ImageQualityMetric(
            QualityMetricCode.SHADOW_CLIPPED_FRACTION,
            "EXPOSURE_CLIPPED_FRACTION_V1",
            1,
            _frac(sum(v <= 0 for v in vals), total),
            QualityMetricUnit.FRACTION,
        ),
        ImageQualityMetric(
            QualityMetricCode.BRIGHT_CLIPPED_FRACTION,
            "EXPOSURE_CLIPPED_FRACTION_V1",
            1,
            _frac(sum(v >= 255 for v in vals), total),
            QualityMetricUnit.FRACTION,
        ),
    )


def evaluate_quality_policy(
    metrics: tuple[ImageQualityMetric, ...], policy: ImageQualityPolicy
) -> tuple[QualityAssessmentStatus, tuple[ImageQualityIssue, ...]]:
    m = {x.metric_code: x.numeric_value for x in metrics}
    sev = {r.issue_code: r.severity for r in policy.severity_rules}
    issues = []
    checks = [
        (
            QualityIssueCode.LOW_RESOLUTION,
            m[QualityMetricCode.SHORT_SIDE_PIXELS] < policy.minimum_short_side_pixels
            or m[QualityMetricCode.LONG_SIDE_PIXELS] < policy.minimum_long_side_pixels,
        ),
        (
            QualityIssueCode.BLUR_DETECTED,
            m[QualityMetricCode.LAPLACIAN_VARIANCE] < policy.blur_minimum_laplacian_variance,
        ),
        (
            QualityIssueCode.LOW_CONTRAST,
            m[QualityMetricCode.LUMINANCE_STANDARD_DEVIATION]
            < policy.contrast_minimum_luminance_stddev,
        ),
        (
            QualityIssueCode.GLARE_DETECTED,
            m[QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION] > policy.glare_maximum_fraction,
        ),
        (
            QualityIssueCode.UNDEREXPOSED,
            m[QualityMetricCode.SHADOW_CLIPPED_FRACTION] > policy.exposure_maximum_shadow_fraction,
        ),
        (
            QualityIssueCode.OVEREXPOSED,
            m[QualityMetricCode.BRIGHT_CLIPPED_FRACTION] > policy.exposure_maximum_bright_fraction,
        ),
    ]
    for code, bad in checks:
        if bad:
            issues.append(ImageQualityIssue(code, sev[code]))
    t = tuple(issues)
    status = (
        QualityAssessmentStatus.GOOD
        if not t
        else (
            QualityAssessmentStatus.RETAKE_REQUIRED
            if any(i.severity is QualityIssueSeverity.BLOCKING for i in t)
            else QualityAssessmentStatus.REVIEW_REQUIRED
        )
    )
    return status, t
