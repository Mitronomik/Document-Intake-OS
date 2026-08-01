"""Strict schema-7 compatibility and schema-8 geometry serialization."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)
from document_intake.domain.value_objects import EntityId
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode

_V7_KEYS = {
    "recipe_version_id",
    "source_file_id",
    "superseded_recipe_version_id",
    "revision",
    "coordinate_space",
    "source_effective_width",
    "source_effective_height",
    "quarter_turn",
    "quadrilateral",
    "pipeline",
    "created_at",
}


def _invalid() -> None:
    raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)


def _dict(value: Any, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _invalid()
    return cast(dict[str, Any], value)


def _string(value: Any) -> str:
    if type(value) is not str:
        _invalid()
    return cast(str, value)


def _integer(value: Any) -> int:
    if type(value) is not int:
        _invalid()
    return cast(int, value)


def _optional_id(value: Any) -> EntityId | None:
    return None if value is None else EntityId.parse(_string(value))


def _time(value: Any) -> datetime:
    result = datetime.fromisoformat(_string(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        _invalid()
    return result


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _point(value: Any) -> GeometryPoint:
    item = _dict(value, {"x", "y"})
    return GeometryPoint(_integer(item["x"]), _integer(item["y"]))


def _quad(value: Any) -> SourceQuadrilateral:
    item = _dict(value, {"top_left", "top_right", "bottom_right", "bottom_left"})
    return SourceQuadrilateral(
        _point(item["top_left"]),
        _point(item["top_right"]),
        _point(item["bottom_right"]),
        _point(item["bottom_left"]),
    )


def image_geometry_recipe_from_json_v7(payload: str, region_id: EntityId) -> ImageGeometryRecipe:
    try:
        item = _dict(json.loads(payload), _V7_KEYS)
        pipeline = _dict(item["pipeline"], {"pipeline_id", "version"})
        return ImageGeometryRecipe(
            EntityId.parse(_string(item["recipe_version_id"])),
            EntityId.parse(_string(item["source_file_id"])),
            _optional_id(item["superseded_recipe_version_id"]),
            _integer(item["revision"]),
            GeometryCoordinateSpace(_string(item["coordinate_space"])),
            _integer(item["source_effective_width"]),
            _integer(item["source_effective_height"]),
            GeometryQuarterTurn(_integer(item["quarter_turn"])),
            _quad(item["quadrilateral"]),
            GeometryPipelineVersion(
                _string(pipeline["pipeline_id"]), _integer(pipeline["version"])
            ),
            _time(item["created_at"]),
            region_id,
        )
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def image_geometry_recipe_to_json(recipe: ImageGeometryRecipe) -> str:
    q = recipe.quadrilateral
    value = {
        "recipe_version_id": str(recipe.recipe_version_id),
        "source_file_id": str(recipe.source_file_id),
        "region_id": str(recipe.region_id),
        "superseded_recipe_version_id": None
        if recipe.superseded_recipe_version_id is None
        else str(recipe.superseded_recipe_version_id),
        "revision": recipe.revision,
        "coordinate_space": recipe.coordinate_space.value,
        "source_effective_width": recipe.source_effective_width,
        "source_effective_height": recipe.source_effective_height,
        "quarter_turn": int(recipe.quarter_turn),
        "quadrilateral": {
            "top_left": {"x": q.top_left.x, "y": q.top_left.y},
            "top_right": {"x": q.top_right.x, "y": q.top_right.y},
            "bottom_right": {"x": q.bottom_right.x, "y": q.bottom_right.y},
            "bottom_left": {"x": q.bottom_left.x, "y": q.bottom_left.y},
        },
        "pipeline": {
            "pipeline_id": recipe.pipeline.pipeline_id,
            "version": recipe.pipeline.version,
        },
        "created_at": _iso(recipe.created_at),
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def image_geometry_recipe_from_json(payload: str) -> ImageGeometryRecipe:
    try:
        raw = json.loads(payload)
        region = EntityId.parse(_string(raw.get("region_id")))
        legacy = {key: value for key, value in raw.items() if key != "region_id"}
        if set(raw) != (_V7_KEYS | {"region_id"}):
            _invalid()
        return image_geometry_recipe_from_json_v7(json.dumps(legacy, separators=(",", ":")), region)
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def image_geometry_recipe_columns(recipe: ImageGeometryRecipe) -> tuple[Any, ...]:
    q = recipe.quadrilateral
    return (
        str(recipe.recipe_version_id),
        str(recipe.source_file_id),
        str(recipe.region_id),
        None
        if recipe.superseded_recipe_version_id is None
        else str(recipe.superseded_recipe_version_id),
        recipe.revision,
        recipe.coordinate_space.value,
        recipe.source_effective_width,
        recipe.source_effective_height,
        int(recipe.quarter_turn),
        q.top_left.x,
        q.top_left.y,
        q.top_right.x,
        q.top_right.y,
        q.bottom_right.x,
        q.bottom_right.y,
        q.bottom_left.x,
        q.bottom_left.y,
        recipe.pipeline.pipeline_id,
        recipe.pipeline.version,
        _iso(recipe.created_at),
    )
