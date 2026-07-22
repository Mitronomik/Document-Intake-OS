"""Deterministic PR-009 whole-frame quality metrics."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext

from document_intake.application.ports.media import DecodedQualityMedia
from document_intake.domain.enums import (
    QualityAssessmentStatus,
    QualityMetricCode,
    QualityMetricUnit,
)
from document_intake.domain.image_quality import (
    ImageQualityIssue,
    ImageQualityMetric,
    ImageQualityPolicy,
    derive_quality_issues_and_status,
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


def calculate_quality_metrics(
    media: DecodedQualityMedia, *, policy: ImageQualityPolicy
) -> tuple[ImageQualityMetric, ...]:
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
            _frac(sum(v >= policy.glare_highlight_cutoff for v in vals), total),
            QualityMetricUnit.FRACTION,
        ),
        ImageQualityMetric(
            QualityMetricCode.SHADOW_CLIPPED_FRACTION,
            "EXPOSURE_CLIPPED_FRACTION_V1",
            1,
            _frac(sum(v <= policy.exposure_shadow_cutoff for v in vals), total),
            QualityMetricUnit.FRACTION,
        ),
        ImageQualityMetric(
            QualityMetricCode.BRIGHT_CLIPPED_FRACTION,
            "EXPOSURE_CLIPPED_FRACTION_V1",
            1,
            _frac(sum(v >= policy.exposure_bright_cutoff for v in vals), total),
            QualityMetricUnit.FRACTION,
        ),
    )


def evaluate_quality_policy(
    metrics: tuple[ImageQualityMetric, ...], policy: ImageQualityPolicy
) -> tuple[QualityAssessmentStatus, tuple[ImageQualityIssue, ...]]:
    """Return status then issues for compatibility with the initial PR-009 service."""
    issues, status = derive_quality_issues_and_status(metrics, policy)
    return status, issues
