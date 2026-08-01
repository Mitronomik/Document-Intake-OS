"""Immutable commands and results for document-region confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NoReturn

from document_intake.domain.document_regions import DocumentRegionSetVersion
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)
from document_intake.domain.value_objects import ActorRef, EntityId


def _invalid(field: str, reason: str = "invalid_type") -> NoReturn:
    raise InvalidValueError(f"{field}: {reason}")


def _require_entity_id(value: object, field: str) -> None:
    if not isinstance(value, EntityId):
        _invalid(field)


def _require_optional_entity_id(value: object, field: str) -> None:
    if value is not None and not isinstance(value, EntityId):
        _invalid(field)


def _require_utc_datetime(value: object) -> None:
    if not isinstance(value, datetime):
        _invalid("confirmed_at")
    if value.tzinfo is None or value.utcoffset() is None:
        _invalid("confirmed_at", "timezone_aware_required")
    if value.utcoffset() != UTC.utcoffset(value):
        _invalid("confirmed_at", "must_be_utc")


@dataclass(frozen=True, slots=True)
class ExistingRecipeSelection:
    geometry_recipe_version_id: EntityId

    def __post_init__(self) -> None:
        _require_entity_id(self.geometry_recipe_version_id, "geometry_recipe_version_id")


@dataclass(frozen=True, slots=True)
class NewRecipeRevision:
    recipe_version_id: EntityId
    superseded_recipe_version_id: EntityId | None
    recipe_revision: int
    quadrilateral: SourceQuadrilateral
    quarter_turn: GeometryQuarterTurn
    recipe_audit_event_id: EntityId

    def __post_init__(self) -> None:
        _require_entity_id(self.recipe_version_id, "recipe_version_id")
        _require_optional_entity_id(
            self.superseded_recipe_version_id, "superseded_recipe_version_id"
        )
        if type(self.recipe_revision) is not int:
            raise InvalidValueError("recipe_revision: invalid_type")
        if self.recipe_revision < 1:
            raise InvalidValueError("recipe_revision: invalid_value")
        if not isinstance(self.quadrilateral, SourceQuadrilateral):
            raise InvalidValueError("quadrilateral: invalid_type")
        if not isinstance(self.quarter_turn, GeometryQuarterTurn):
            raise InvalidValueError("quarter_turn: invalid_type")
        if not isinstance(self.recipe_audit_event_id, EntityId):
            raise InvalidValueError("recipe_audit_event_id: invalid_type")


RecipeSelection = ExistingRecipeSelection | NewRecipeRevision


@dataclass(frozen=True, slots=True)
class RegionSetMemberInput:
    order_index: int
    region_id: EntityId
    recipe_selection: RecipeSelection

    def __post_init__(self) -> None:
        if type(self.order_index) is not int:
            raise InvalidValueError("order_index: invalid_type")
        _require_entity_id(self.region_id, "region_id")
        if not isinstance(self.recipe_selection, (ExistingRecipeSelection, NewRecipeRevision)):
            raise InvalidValueError("recipe_selection: invalid_type")


@dataclass(frozen=True, slots=True)
class ConfirmDocumentRegionsCommand:
    region_set_version_id: EntityId
    source_file_id: EntityId
    superseded_region_set_version_id: EntityId | None
    set_revision: int
    members: tuple[RegionSetMemberInput, ...]
    region_set_audit_event_id: EntityId
    confirmed_at: datetime
    actor: ActorRef
    correlation_id: EntityId | None

    def __post_init__(self) -> None:
        _require_entity_id(self.region_set_version_id, "region_set_version_id")
        _require_entity_id(self.source_file_id, "source_file_id")
        _require_optional_entity_id(
            self.superseded_region_set_version_id, "superseded_region_set_version_id"
        )
        if type(self.set_revision) is not int:
            raise InvalidValueError("set_revision: invalid_type")
        if self.set_revision < 1:
            raise InvalidValueError("set_revision: invalid_value")
        if not isinstance(self.members, tuple) or not all(
            isinstance(member, RegionSetMemberInput) for member in self.members
        ):
            raise InvalidValueError("members: invalid_type")
        _require_entity_id(self.region_set_audit_event_id, "region_set_audit_event_id")
        _require_utc_datetime(self.confirmed_at)
        if not isinstance(self.actor, ActorRef):
            raise InvalidValueError("actor: invalid_type")
        _require_optional_entity_id(self.correlation_id, "correlation_id")


@dataclass(frozen=True, slots=True)
class ConfirmDocumentRegionsResult:
    region_set: DocumentRegionSetVersion
    selected_recipes: tuple[ImageGeometryRecipe, ...]
