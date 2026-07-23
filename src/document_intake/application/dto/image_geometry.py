"""PR-010 image geometry DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryPipelineVersion,
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)
from document_intake.domain.value_objects import ActorRef, EntityId


@dataclass(frozen=True, slots=True)
class CreateImageGeometryRecipeCommand:
    recipe_version_id: EntityId
    source_file_id: EntityId
    superseded_recipe_version_id: EntityId | None
    revision: int
    expected_source_effective_width: int
    expected_source_effective_height: int
    quadrilateral: SourceQuadrilateral
    quarter_turn: GeometryQuarterTurn
    pipeline: GeometryPipelineVersion
    created_at: datetime
    actor: ActorRef
    audit_event_id: EntityId
    correlation_id: EntityId

    def __post_init__(self) -> None:
        for n in ("recipe_version_id", "source_file_id", "audit_event_id", "correlation_id"):
            if not isinstance(getattr(self, n), EntityId):
                raise InvalidValueError(f"create_image_geometry_recipe_command.{n}: invalid_type")
        if self.recipe_version_id == self.audit_event_id:
            raise InvalidValueError("create_image_geometry_recipe_command.ids: not_distinct")
        if self.superseded_recipe_version_id is not None and not isinstance(
            self.superseded_recipe_version_id, EntityId
        ):
            raise InvalidValueError(
                "create_image_geometry_recipe_command.superseded_recipe_version_id: invalid_type"
            )
        if type(self.revision) is not int or self.revision < 1:
            raise InvalidValueError("create_image_geometry_recipe_command.revision: invalid_value")
        for n in ("expected_source_effective_width", "expected_source_effective_height"):
            if type(getattr(self, n)) is not int or getattr(self, n) < 1:
                raise InvalidValueError(f"create_image_geometry_recipe_command.{n}: invalid_value")
        if not isinstance(self.quadrilateral, SourceQuadrilateral):
            raise InvalidValueError(
                "create_image_geometry_recipe_command.quadrilateral: invalid_type"
            )
        if not isinstance(self.quarter_turn, GeometryQuarterTurn):
            raise InvalidValueError(
                "create_image_geometry_recipe_command.quarter_turn: invalid_type"
            )
        if not isinstance(self.pipeline, GeometryPipelineVersion):
            raise InvalidValueError("create_image_geometry_recipe_command.pipeline: invalid_type")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise InvalidValueError(
                "create_image_geometry_recipe_command.created_at: timezone_required"
            )
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        if not isinstance(self.actor, ActorRef):
            raise InvalidValueError("create_image_geometry_recipe_command.actor: invalid_type")


@dataclass(frozen=True, slots=True)
class CreateImageGeometryRecipeResult:
    recipe: ImageGeometryRecipe
    rendered_width: int
    rendered_height: int
    pipeline: GeometryPipelineVersion

    def __post_init__(self) -> None:
        if not isinstance(self.recipe, ImageGeometryRecipe):
            raise InvalidValueError("create_image_geometry_recipe_result.recipe: invalid_type")
        if (
            type(self.rendered_width) is not int
            or self.rendered_width < 1
            or type(self.rendered_height) is not int
            or self.rendered_height < 1
        ):
            raise InvalidValueError(
                "create_image_geometry_recipe_result.rendered_dimensions: invalid_value"
            )
        if not isinstance(self.pipeline, GeometryPipelineVersion):
            raise InvalidValueError("create_image_geometry_recipe_result.pipeline: invalid_type")
