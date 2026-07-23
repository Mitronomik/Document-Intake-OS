from datetime import UTC, datetime
from uuid import uuid4

from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)
from document_intake.domain.value_objects import EntityId
from document_intake.persistence.serialization import (
    image_geometry_recipe_from_json,
    image_geometry_recipe_to_json,
)


def eid():
    return EntityId(uuid4())


def test_geometry_recipe_canonical_round_trip():
    r = ImageGeometryRecipe(
        eid(),
        eid(),
        None,
        1,
        GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
        4,
        4,
        GeometryQuarterTurn.DEG_0,
        SourceQuadrilateral(
            GeometryPoint(0, 0), GeometryPoint(4, 0), GeometryPoint(4, 4), GeometryPoint(0, 4)
        ),
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        datetime(2026, 7, 23, tzinfo=UTC),
    )
    assert image_geometry_recipe_from_json(image_geometry_recipe_to_json(r)) == r
