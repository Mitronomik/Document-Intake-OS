"""Immutable operator-confirmed document-region aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId


class DocumentRegionErrorCode(StrEnum):
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    REGION_COUNT_INVALID = "REGION_COUNT_INVALID"
    REGION_ORDER_INVALID = "REGION_ORDER_INVALID"
    REGION_SELECTION_INVALID = "REGION_SELECTION_INVALID"
    REGION_IDENTITY_CONFLICT = "REGION_IDENTITY_CONFLICT"
    DUPLICATE_REGION = "DUPLICATE_REGION"
    REGION_REVISION_CONFLICT = "REGION_REVISION_CONFLICT"
    REGION_SET_REVISION_CONFLICT = "REGION_SET_REVISION_CONFLICT"
    REGION_SET_NOT_FOUND = "REGION_SET_NOT_FOUND"
    PERSISTENCE_CONFLICT = "PERSISTENCE_CONFLICT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    PERSISTED_DATA_INVALID = "PERSISTED_DATA_INVALID"
    COMMIT_FAILED = "COMMIT_FAILED"


@dataclass(frozen=True, slots=True)
class DocumentRegionSetMember:
    order_index: int
    region_id: EntityId
    geometry_recipe_version_id: EntityId

    def __post_init__(self) -> None:
        if type(self.order_index) is not int or self.order_index not in (1, 2):
            raise InvalidValueError(DocumentRegionErrorCode.REGION_ORDER_INVALID.value)
        if not isinstance(self.region_id, EntityId) or not isinstance(
            self.geometry_recipe_version_id, EntityId
        ):
            raise InvalidValueError(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT.value)

    def __repr__(self) -> str:
        return f"DocumentRegionSetMember(order_index={self.order_index}, <redacted>)"


@dataclass(frozen=True, slots=True)
class DocumentRegionSetVersion:
    region_set_version_id: EntityId
    source_file_id: EntityId
    superseded_region_set_version_id: EntityId | None
    revision: int
    members: tuple[DocumentRegionSetMember, ...]
    confirmed_at: datetime
    confirmed_by: ActorRef

    def __post_init__(self) -> None:
        self._validate_identity_and_revision()
        self._validate_members()
        self._normalize_confirmation()

    def _validate_identity_and_revision(self) -> None:
        if not isinstance(self.region_set_version_id, EntityId) or not isinstance(
            self.source_file_id, EntityId
        ):
            raise InvalidValueError(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT.value)
        if type(self.revision) is not int or self.revision < 1:
            raise InvalidValueError(DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT.value)
        if (self.revision == 1) != (self.superseded_region_set_version_id is None):
            raise InvalidValueError(DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT.value)

    def _validate_members(self) -> None:
        if len(self.members) not in (1, 2):
            raise InvalidValueError(DocumentRegionErrorCode.REGION_COUNT_INVALID.value)
        if not all(isinstance(x, DocumentRegionSetMember) for x in self.members):
            raise InvalidValueError(DocumentRegionErrorCode.REGION_SELECTION_INVALID.value)
        if tuple(x.order_index for x in self.members) != tuple(range(1, len(self.members) + 1)):
            raise InvalidValueError(DocumentRegionErrorCode.REGION_ORDER_INVALID.value)
        if len({x.region_id for x in self.members}) != len(self.members) or len(
            {x.geometry_recipe_version_id for x in self.members}
        ) != len(self.members):
            raise InvalidValueError(DocumentRegionErrorCode.DUPLICATE_REGION.value)

    def _normalize_confirmation(self) -> None:
        if not isinstance(self.confirmed_at, datetime) or self.confirmed_at.tzinfo is None:
            raise InvalidValueError("document_region_set.confirmed_at: timezone_required")
        if not isinstance(self.confirmed_by, ActorRef):
            raise InvalidValueError("document_region_set.confirmed_by: invalid_type")
        object.__setattr__(self, "confirmed_at", self.confirmed_at.astimezone(UTC))

    def __repr__(self) -> str:
        return (
            f"DocumentRegionSetVersion(revision={self.revision}, "
            f"member_count={len(self.members)}, <redacted>)"
        )
