"""Immutable commands and results for document-region confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from document_intake.domain.document_regions import DocumentRegionSetVersion
from document_intake.domain.image_geometry import (
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)
from document_intake.domain.value_objects import ActorRef, EntityId


@dataclass(frozen=True, slots=True)
class ExistingRecipeSelection:
    geometry_recipe_version_id: EntityId


@dataclass(frozen=True, slots=True)
class NewRecipeRevision:
    recipe_version_id: EntityId
    superseded_recipe_version_id: EntityId | None
    recipe_revision: int
    quadrilateral: SourceQuadrilateral
    quarter_turn: GeometryQuarterTurn
    recipe_audit_event_id: EntityId


RecipeSelection = ExistingRecipeSelection | NewRecipeRevision


@dataclass(frozen=True, slots=True)
class RegionSetMemberInput:
    order_index: int
    region_id: EntityId
    recipe_selection: RecipeSelection


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


@dataclass(frozen=True, slots=True)
class ConfirmDocumentRegionsResult:
    region_set: DocumentRegionSetVersion
    selected_recipes: tuple[ImageGeometryRecipe, ...]
