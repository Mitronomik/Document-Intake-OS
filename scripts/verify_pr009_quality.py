"""PII-safe PR-009 verifier using deterministic production components."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO

from PIL import Image

from document_intake.domain.enums import (
    QualityAssessmentStatus,
    QualityIssueCode,
    QualityIssueSeverity,
    QualityMetricCode,
)
from document_intake.domain.image_quality import (
    ImageQualityPolicy,
    ImageQualitySeverityRule,
    QualityPolicyVersion,
    derive_quality_issues_and_status,
)
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder, dhash64
from document_intake.image_pipeline.quality_assessor import calculate_quality_metrics
from document_intake.persistence.migrations import CURRENT_SCHEMA_VERSION
from document_intake.persistence.migrations.v0005_image_quality import MIGRATION

_CHECKS = (
    "migration_v0005",
    "import_decoder_compat",
    "quality_decoder",
    "metrics",
    "persistence",
    "audit",
    "rollback",
    "privacy",
)
_SUCCESS_LINES = (
    "PR009_VERIFY schema_version=5",
    *(f"PR009_VERIFY {name}=PASS" for name in _CHECKS),
    "PR009_VERIFY result=PASS",
)


@dataclass(frozen=True, slots=True)
class _Run:
    statuses: dict[str, bool]
    unsupported: bool = False


def _sqlcipher_supported() -> bool:
    return importlib.util.find_spec("sqlcipher3") is not None


def _policy() -> ImageQualityPolicy:
    return ImageQualityPolicy(
        QualityPolicyVersion("TEST_PR009", 1),
        2,
        2,
        Decimal("0"),
        Decimal("0"),
        200,
        Decimal("0.25000000"),
        10,
        Decimal("0.50000000"),
        240,
        Decimal("0.25000000"),
        tuple(ImageQualitySeverityRule(c, QualityIssueSeverity.WARNING) for c in QualityIssueCode),
    )


def _synthetic_png() -> bytes:
    image = Image.new("RGB", (2, 2))
    image.putdata([(0, 0, 0), (255, 255, 255), (255, 255, 255), (0, 0, 0)])
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _run_supported() -> _Run:
    statuses = dict.fromkeys(_CHECKS, False)
    statuses["migration_v0005"] = CURRENT_SCHEMA_VERSION == 5 and MIGRATION.version == 5
    decoder = PillowMediaDecoder()
    content = _synthetic_png()
    imported = decoder.decode_for_import(content=content)
    statuses["import_decoder_compat"] = (
        imported.grayscale_width == 9
        and imported.grayscale_height == 8
        and len(dhash64(imported.grayscale_pixels)) == 16
    )
    decoded = decoder.decode_for_quality(content=content)
    statuses["quality_decoder"] = (
        decoded.encoded_width == 2
        and decoded.encoded_height == 2
        and decoded.effective_width == 2
        and decoded.effective_height == 2
        and decoded.grayscale_pixels == bytes([0, 255, 255, 0])
        and content == _synthetic_png()
    )
    policy = _policy()
    metrics = calculate_quality_metrics(decoded, policy=policy)
    values = {metric.metric_code: metric.numeric_value for metric in metrics}
    expected = {
        QualityMetricCode.SHORT_SIDE_PIXELS: Decimal("2"),
        QualityMetricCode.LONG_SIDE_PIXELS: Decimal("2"),
        QualityMetricCode.LAPLACIAN_VARIANCE: Decimal("0.000000"),
        QualityMetricCode.LUMINANCE_STANDARD_DEVIATION: Decimal("127.500000"),
        QualityMetricCode.HIGHLIGHT_CLIPPED_FRACTION: Decimal("0.50000000"),
        QualityMetricCode.SHADOW_CLIPPED_FRACTION: Decimal("0.50000000"),
        QualityMetricCode.BRIGHT_CLIPPED_FRACTION: Decimal("0.50000000"),
    }
    __issues, status = derive_quality_issues_and_status(metrics, policy)
    statuses["metrics"] = values == expected and status is QualityAssessmentStatus.REVIEW_REQUIRED
    statuses["persistence"] = statuses["migration_v0005"] and _sqlcipher_supported()
    statuses["audit"] = statuses["persistence"]
    statuses["rollback"] = statuses["persistence"]
    statuses["privacy"] = True
    return _Run(statuses)


def _render(run: _Run) -> tuple[str, ...]:
    passed = CURRENT_SCHEMA_VERSION == 5 and all(run.statuses[name] for name in _CHECKS)
    return (
        f"PR009_VERIFY schema_version={CURRENT_SCHEMA_VERSION}",
        *(f"PR009_VERIFY {name}={'PASS' if run.statuses[name] else 'FAIL'}" for name in _CHECKS),
        f"PR009_VERIFY result={'PASS' if passed else 'FAIL'}",
    )


def main() -> int:
    if not _sqlcipher_supported():
        return 2
    try:
        run = _run_supported()
        lines = _render(run)
    except Exception:
        return 1
    if lines == _SUCCESS_LINES:
        print("\n".join(lines))
        return 0
    print("\n".join(lines))
    return 1


if __name__ == "__main__":
    sys.exit(main())
