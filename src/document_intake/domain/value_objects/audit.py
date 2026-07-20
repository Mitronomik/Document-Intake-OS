"""PII-safe audit value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass

from document_intake.domain.enums import AuditValueClassification
from document_intake.domain.errors import InvalidValueError

_REASON_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_DISPLAY_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{0,63}$")


@dataclass(frozen=True, slots=True, order=True)
class AuditReasonCode:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidValueError("audit_reason_code: invalid_type")
        if not _REASON_RE.fullmatch(self.value):
            raise InvalidValueError("audit_reason_code: invalid_format")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class AuditValueSummary:
    classification: AuditValueClassification
    display_value: str | None
    was_present: bool

    def __post_init__(self) -> None:
        if not isinstance(self.classification, AuditValueClassification):
            raise InvalidValueError("audit_value_summary.classification: invalid_type")
        if not isinstance(self.was_present, bool):
            raise InvalidValueError("audit_value_summary.was_present: invalid_type")
        if self.display_value is not None and not isinstance(self.display_value, str):
            raise InvalidValueError("audit_value_summary.display_value: invalid_type")
        if self.classification is AuditValueClassification.ABSENT:
            if self.was_present or self.display_value is not None:
                raise InvalidValueError("audit_value_summary.ABSENT: invalid_combination")
        elif self.classification is AuditValueClassification.NON_SENSITIVE:
            if not self.was_present:
                raise InvalidValueError("audit_value_summary.NON_SENSITIVE: presence_required")
            if self.display_value is None or not _DISPLAY_RE.fullmatch(self.display_value):
                raise InvalidValueError("audit_value_summary.NON_SENSITIVE: invalid_display_value")
        elif self.classification is AuditValueClassification.SENSITIVE_REDACTED and (
            not self.was_present or self.display_value is not None
        ):
            raise InvalidValueError("audit_value_summary.SENSITIVE_REDACTED: invalid_combination")
