"""Immutable PR-010 image geometry recipe domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import IntEnum, StrEnum

from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import EntityId

PIPELINE_ID = "PILLOW_QUAD_BICUBIC"
PIPELINE_VERSION = 1


class GeometryCoordinateSpace(StrEnum):
    SOURCE_EFFECTIVE_PIXELS_V1 = "SOURCE_EFFECTIVE_PIXELS_V1"


class GeometryQuarterTurn(IntEnum):
    DEG_0 = 0
    DEG_90 = 90
    DEG_180 = 180
    DEG_270 = 270


class GeometryErrorCode(StrEnum):
    SOURCE_FILE_NOT_FOUND = "SOURCE_FILE_NOT_FOUND"
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
    ARTIFACT_INTEGRITY_FAILED = "ARTIFACT_INTEGRITY_FAILED"
    DECODE_FAILED = "DECODE_FAILED"
    SOURCE_DIMENSIONS_MISMATCH = "SOURCE_DIMENSIONS_MISMATCH"
    POINT_OUT_OF_BOUNDS = "POINT_OUT_OF_BOUNDS"
    DUPLICATE_POINT = "DUPLICATE_POINT"
    NON_CLOCKWISE_QUADRILATERAL = "NON_CLOCKWISE_QUADRILATERAL"
    SELF_INTERSECTING_QUADRILATERAL = "SELF_INTERSECTING_QUADRILATERAL"
    NON_CONVEX_QUADRILATERAL = "NON_CONVEX_QUADRILATERAL"
    AREA_TOO_SMALL = "AREA_TOO_SMALL"
    OUTPUT_DIMENSIONS_TOO_SMALL = "OUTPUT_DIMENSIONS_TOO_SMALL"
    INVALID_QUARTER_TURN = "INVALID_QUARTER_TURN"
    INVALID_PIPELINE_VERSION = "INVALID_PIPELINE_VERSION"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    RENDER_FAILED = "RENDER_FAILED"
    RECIPE_PERSISTENCE_FAILED = "RECIPE_PERSISTENCE_FAILED"
    AUDIT_PERSISTENCE_FAILED = "AUDIT_PERSISTENCE_FAILED"
    COMMIT_FAILED = "COMMIT_FAILED"


@dataclass(frozen=True, slots=True)
class GeometryPipelineVersion:
    pipeline_id: str
    version: int

    def __post_init__(self) -> None:
        if type(self.pipeline_id) is not str or self.pipeline_id != PIPELINE_ID:
            raise InvalidValueError("geometry_pipeline_version.pipeline_id: invalid_value")
        if type(self.version) is not int or self.version != PIPELINE_VERSION:
            raise InvalidValueError("geometry_pipeline_version.version: invalid_value")

    def __repr__(self) -> str:
        return f"GeometryPipelineVersion(pipeline_id={self.pipeline_id!r}, version={self.version})"


@dataclass(frozen=True, slots=True, order=True)
class GeometryPoint:
    x: int
    y: int

    def __post_init__(self) -> None:
        if type(self.x) is not int or type(self.y) is not int:
            raise InvalidValueError("geometry_point: invalid_type")


@dataclass(frozen=True, slots=True)
class SourceQuadrilateral:
    top_left: GeometryPoint
    top_right: GeometryPoint
    bottom_right: GeometryPoint
    bottom_left: GeometryPoint

    def __post_init__(self) -> None:
        for p in self.points:
            if not isinstance(p, GeometryPoint):
                raise InvalidValueError("source_quadrilateral.point: invalid_type")

    @property
    def points(self) -> tuple[GeometryPoint, GeometryPoint, GeometryPoint, GeometryPoint]:
        return (self.top_left, self.top_right, self.bottom_right, self.bottom_left)

    def validate_for_source(self, width: int, height: int) -> tuple[int, int]:
        if type(width) is not int or type(height) is not int or width < 1 or height < 1:
            raise InvalidValueError(GeometryErrorCode.SOURCE_DIMENSIONS_MISMATCH.value)
        for p in self.points:
            if not (0 <= p.x <= width and 0 <= p.y <= height):
                raise InvalidValueError(GeometryErrorCode.POINT_OUT_OF_BOUNDS.value)
        if len(set(self.points)) != 4:
            raise InvalidValueError(GeometryErrorCode.DUPLICATE_POINT.value)
        area2 = _signed_twice_area(self.points)
        if area2 <= 0:
            raise InvalidValueError(GeometryErrorCode.NON_CLOCKWISE_QUADRILATERAL.value)
        if _segments_intersect(
            self.top_left, self.top_right, self.bottom_right, self.bottom_left
        ) or _segments_intersect(
            self.top_right, self.bottom_right, self.bottom_left, self.top_left
        ):
            raise InvalidValueError(GeometryErrorCode.SELF_INTERSECTING_QUADRILATERAL.value)
        crosses = [
            _cross(self.points[i], self.points[(i + 1) % 4], self.points[(i + 2) % 4])
            for i in range(4)
        ]
        if any(c <= 0 for c in crosses):
            raise InvalidValueError(GeometryErrorCode.NON_CONVEX_QUADRILATERAL.value)
        if area2 < 8:
            raise InvalidValueError(GeometryErrorCode.AREA_TOO_SMALL.value)
        return derive_geometry_dimensions(self, GeometryQuarterTurn.DEG_0)

    def __repr__(self) -> str:
        return "SourceQuadrilateral(point_count=4)"


def _signed_twice_area(points: tuple[GeometryPoint, ...]) -> int:
    return sum(p.x * q.y - p.y * q.x for p, q in zip(points, (*points[1:], points[0]), strict=True))


def _cross(a: GeometryPoint, b: GeometryPoint, c: GeometryPoint) -> int:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _orientation(a: GeometryPoint, b: GeometryPoint, c: GeometryPoint) -> int:
    v = _cross(a, b, c)
    return (v > 0) - (v < 0)


def _on_segment(a: GeometryPoint, b: GeometryPoint, c: GeometryPoint) -> bool:
    return min(a.x, c.x) <= b.x <= max(a.x, c.x) and min(a.y, c.y) <= b.y <= max(a.y, c.y)


def _segments_intersect(
    a: GeometryPoint, b: GeometryPoint, c: GeometryPoint, d: GeometryPoint
) -> bool:
    o1, o2, o3, o4 = (
        _orientation(a, b, c),
        _orientation(a, b, d),
        _orientation(c, d, a),
        _orientation(c, d, b),
    )
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and _on_segment(a, c, b))
        or (o2 == 0 and _on_segment(a, d, b))
        or (o3 == 0 and _on_segment(c, a, d))
        or (o4 == 0 and _on_segment(c, b, d))
    )


def _distance(a: GeometryPoint, b: GeometryPoint) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        dx = Decimal(b.x - a.x)
        dy = Decimal(b.y - a.y)
        return ctx.sqrt(dx * dx + dy * dy)


def derive_geometry_dimensions(
    q: SourceQuadrilateral, turn: GeometryQuarterTurn
) -> tuple[int, int]:
    if not isinstance(turn, GeometryQuarterTurn):
        raise InvalidValueError(GeometryErrorCode.INVALID_QUARTER_TURN.value)
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        w = max(
            _distance(q.top_left, q.top_right), _distance(q.bottom_left, q.bottom_right)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        h = max(
            _distance(q.top_left, q.bottom_left), _distance(q.top_right, q.bottom_right)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    iw, ih = int(w), int(h)
    if iw < 2 or ih < 2:
        raise InvalidValueError(GeometryErrorCode.OUTPUT_DIMENSIONS_TOO_SMALL.value)
    if turn in {GeometryQuarterTurn.DEG_90, GeometryQuarterTurn.DEG_270}:
        return ih, iw
    return iw, ih


@dataclass(frozen=True, slots=True)
class ImageGeometryRecipe:
    recipe_version_id: EntityId
    source_file_id: EntityId
    superseded_recipe_version_id: EntityId | None
    revision: int
    coordinate_space: GeometryCoordinateSpace
    source_effective_width: int
    source_effective_height: int
    quarter_turn: GeometryQuarterTurn
    quadrilateral: SourceQuadrilateral
    pipeline: GeometryPipelineVersion
    created_at: datetime

    def __post_init__(self) -> None:
        for n in ("recipe_version_id", "source_file_id"):
            if not isinstance(getattr(self, n), EntityId):
                raise InvalidValueError(f"image_geometry_recipe.{n}: invalid_type")
        if self.superseded_recipe_version_id is not None and not isinstance(
            self.superseded_recipe_version_id, EntityId
        ):
            raise InvalidValueError(
                "image_geometry_recipe.superseded_recipe_version_id: invalid_type"
            )
        if type(self.revision) is not int or self.revision < 1:
            raise InvalidValueError("image_geometry_recipe.revision: invalid_value")
        if (self.revision == 1) != (self.superseded_recipe_version_id is None):
            raise InvalidValueError("image_geometry_recipe.revision_chain: invalid_value")
        if not isinstance(self.coordinate_space, GeometryCoordinateSpace):
            raise InvalidValueError("image_geometry_recipe.coordinate_space: invalid_type")
        if (
            type(self.source_effective_width) is not int
            or self.source_effective_width < 1
            or type(self.source_effective_height) is not int
            or self.source_effective_height < 1
        ):
            raise InvalidValueError("image_geometry_recipe.source_dimensions: invalid_value")
        if not isinstance(self.quarter_turn, GeometryQuarterTurn):
            raise InvalidValueError(GeometryErrorCode.INVALID_QUARTER_TURN.value)
        if not isinstance(self.quadrilateral, SourceQuadrilateral):
            raise InvalidValueError("image_geometry_recipe.quadrilateral: invalid_type")
        self.quadrilateral.validate_for_source(
            self.source_effective_width, self.source_effective_height
        )
        derive_geometry_dimensions(self.quadrilateral, self.quarter_turn)
        if not isinstance(self.pipeline, GeometryPipelineVersion):
            raise InvalidValueError(GeometryErrorCode.INVALID_PIPELINE_VERSION.value)
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise InvalidValueError("image_geometry_recipe.created_at: timezone_required")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))

    def __repr__(self) -> str:
        return (
            "ImageGeometryRecipe("
            f"recipe_version_id={self.recipe_version_id}, "
            f"source_file_id={self.source_file_id}, revision={self.revision}, "
            f"coordinate_space={self.coordinate_space.value}, "
            f"quarter_turn={int(self.quarter_turn)}, pipeline={self.pipeline!r})"
        )
