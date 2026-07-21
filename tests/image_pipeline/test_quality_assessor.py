from decimal import Decimal

from document_intake.application.ports.media import DecodedQualityMedia
from document_intake.domain.enums import (
    QualityIssueCode,
    QualityIssueSeverity,
    QualityMetricCode,
    SourceMediaType,
)
from document_intake.domain.image_quality import (
    ImageQualityPolicy,
    ImageQualitySeverityRule,
    QualityPolicyVersion,
)
from document_intake.image_pipeline.quality_assessor import (
    calculate_quality_metrics,
    evaluate_quality_policy,
)


def policy(**kw) -> ImageQualityPolicy:
    base = dict(
        version=QualityPolicyVersion("TEST_PR009", 1),
        minimum_short_side_pixels=1,
        minimum_long_side_pixels=1,
        blur_minimum_laplacian_variance=Decimal("0"),
        contrast_minimum_luminance_stddev=Decimal("0"),
        glare_highlight_cutoff=200,
        glare_maximum_fraction=Decimal("1"),
        exposure_shadow_cutoff=10,
        exposure_maximum_shadow_fraction=Decimal("1"),
        exposure_bright_cutoff=240,
        exposure_maximum_bright_fraction=Decimal("1"),
        severity_rules=tuple(
            ImageQualitySeverityRule(c, QualityIssueSeverity.WARNING) for c in QualityIssueCode
        ),
    )
    base.update(kw)
    return ImageQualityPolicy(**base)


def media(px: bytes, w: int = 2, h: int = 2):
    return DecodedQualityMedia(SourceMediaType.PNG, w, h, None, w, h, px, w, h)


def test_policy_cutoffs_and_vectors() -> None:
    p = policy(
        glare_highlight_cutoff=200,
        exposure_shadow_cutoff=10,
        exposure_bright_cutoff=240,
        glare_maximum_fraction=Decimal("0.5"),
        exposure_maximum_bright_fraction=Decimal("0.5"),
    )
    m = calculate_quality_metrics(media(bytes([0, 0, 255, 255])), policy=p)
    vals = {x.metric_code: x.numeric_value for x in m}
    assert vals[QualityMetricCode.SHORT_SIDE_PIXELS] == Decimal("2")
    assert vals[QualityMetricCode.LONG_SIDE_PIXELS] == Decimal("2")
    assert vals[QualityMetricCode.LUMINANCE_STANDARD_DEVIATION] == Decimal("127.500000")
    assert vals[QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION] == Decimal("0.50000000")
    assert vals[QualityMetricCode.SHADOW_CLIPPED_FRACTION] == Decimal("0.50000000")
    assert vals[QualityMetricCode.BRIGHT_CLIPPED_FRACTION] == Decimal("0.50000000")
    _status, issues = evaluate_quality_policy(m, p)
    assert QualityIssueCode.GLARE_DETECTED not in [i.issue_code for i in issues]
    p2 = policy(
        glare_highlight_cutoff=255,
        glare_maximum_fraction=Decimal("0.25"),
        exposure_bright_cutoff=255,
        exposure_maximum_bright_fraction=Decimal("0.25"),
    )
    m2 = calculate_quality_metrics(media(bytes([0, 254, 255, 255])), policy=p2)
    vals2 = {x.metric_code: x.numeric_value for x in m2}
    assert vals2[QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION] == Decimal("0.50000000")
    __status, issues = evaluate_quality_policy(m2, p2)
    assert {i.issue_code for i in issues} >= {
        QualityIssueCode.GLARE_DETECTED,
        QualityIssueCode.OVEREXPOSED,
    }
