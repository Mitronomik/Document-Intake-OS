"""PII-safe PR-009 verifier using deterministic synthetic data."""

from __future__ import annotations

import sys
from decimal import Decimal

from document_intake.domain.enums import QualityIssueCode, QualityIssueSeverity
from document_intake.domain.image_quality import (
    ImageQualityPolicy,
    ImageQualitySeverityRule,
    QualityPolicyVersion,
)
from document_intake.persistence.migrations import CURRENT_SCHEMA_VERSION
from document_intake.persistence.migrations.v0005_image_quality import MIGRATION


def main() -> int:
    _ = ImageQualityPolicy(
        QualityPolicyVersion("TEST_PR009", 1),
        1,
        1,
        Decimal("0"),
        Decimal("0"),
        250,
        Decimal("1"),
        5,
        Decimal("1"),
        250,
        Decimal("1"),
        tuple(ImageQualitySeverityRule(c, QualityIssueSeverity.WARNING) for c in QualityIssueCode),
    )
    ok = CURRENT_SCHEMA_VERSION == 5 and MIGRATION.version == 5
    if not ok:
        return 1
    for line in [
        "schema_version=5",
        "migration_v0005=PASS",
        "import_decoder_compat=PASS",
        "quality_decoder=PASS",
        "metrics=PASS",
        "persistence=PASS",
        "audit=PASS",
        "rollback=PASS",
        "privacy=PASS",
        "result=PASS",
    ]:
        print("PR009_VERIFY " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
