"""Core immutable value objects."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any
from uuid import UUID

from document_intake.domain.enums import ActorKind, OwnerKind
from document_intake.domain.errors import InvalidValueError

_FIELD_KEY_RE = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)*$")


def _reject_padded_text(value: str, invariant: str) -> None:
    if not isinstance(value, str):
        raise InvalidValueError(f"{invariant}: invalid_type")
    if not value or not value.strip():
        raise InvalidValueError(f"{invariant}: empty")
    if value != value.strip():
        raise InvalidValueError(f"{invariant}: surrounding_whitespace")


@dataclass(frozen=True, slots=True, order=True)
class EntityId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise InvalidValueError("entity_id: invalid_type")

    @classmethod
    def parse(cls, value: str) -> EntityId:
        try:
            return cls(UUID(value))
        except (AttributeError, TypeError, ValueError) as exc:
            raise InvalidValueError("entity_id: invalid_uuid") from exc

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True, order=True)
class NonEmptyText:
    value: str

    def __post_init__(self) -> None:
        _reject_padded_text(self.value, "non_empty_text")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return "NonEmptyText(<redacted>)"


@dataclass(frozen=True, slots=True, order=True)
class IdentifierText:
    value: str

    def __post_init__(self) -> None:
        _reject_padded_text(self.value, "identifier_text")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return "IdentifierText(<redacted>)"


@dataclass(frozen=True, slots=True, order=True)
class CountryCode:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidValueError("country_code: invalid_type")
        if not re.fullmatch(r"[A-Z]{2,3}", self.value):
            raise InvalidValueError("country_code: invalid_format")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class FieldKey:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidValueError("field_key: invalid_type")
        if not _FIELD_KEY_RE.fullmatch(self.value):
            raise InvalidValueError("field_key: invalid_format")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class FieldRef:
    entity_id: EntityId
    field_key: FieldKey


@dataclass(frozen=True, slots=True, order=True)
class Confidence:
    value: Decimal

    def __init__(self, value: Decimal | int | str | float) -> None:
        if isinstance(value, bool):
            raise InvalidValueError("confidence: invalid_type")
        try:
            decimal_value = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise InvalidValueError("confidence: invalid_decimal") from exc
        object.__setattr__(self, "value", decimal_value)
        if decimal_value.is_nan() or decimal_value.is_infinite():
            raise InvalidValueError("confidence: finite_required")
        if not Decimal("0") <= decimal_value <= Decimal("1"):
            raise InvalidValueError("confidence: out_of_range")


@dataclass(frozen=True, slots=True, order=True)
class ActorRef:
    actor_id: EntityId
    kind: ActorKind


@dataclass(frozen=True, slots=True, order=True)
class OwnerRef:
    owner_kind: OwnerKind
    owner_id: EntityId


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: NonEmptyText
    message: NonEmptyText
    blocking: bool
    field_ref: FieldRef | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

    @property
    def has_blocking_issues(self) -> bool:
        return any(issue.blocking for issue in self.issues)

    @property
    def blocking_issues(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)


JsonValue = str | int | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def _canonicalize(value: Any) -> JsonValue:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise InvalidValueError("snapshot_payload: float_forbidden")
    if isinstance(value, list | tuple):
        return [_canonicalize(item) for item in value]
    if isinstance(value, dict | MappingProxyType):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise InvalidValueError("snapshot_payload: non_string_key")
            result[key] = _canonicalize(item)
        return result
    raise InvalidValueError("snapshot_payload: unsupported_type")


@dataclass(frozen=True, slots=True)
class SnapshotPayload:
    canonical_json: str

    def __init__(self, value: dict[str, Any] | str) -> None:
        loaded = json.loads(value) if isinstance(value, str) else value
        if not isinstance(loaded, dict):
            raise InvalidValueError("snapshot_payload: root_mapping_required")
        canonical = _canonicalize(loaded)
        encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        object.__setattr__(self, "canonical_json", encoded)

    def as_dict(self) -> dict[str, JsonValue]:
        decoded = json.loads(self.canonical_json)
        if not isinstance(decoded, dict):  # defensive; constructor prevents this.
            raise InvalidValueError("snapshot_payload: root_mapping_required")
        return decoded

    def __repr__(self) -> str:
        return "SnapshotPayload(<canonical_json>)"
