from datetime import UTC, datetime
from uuid import uuid4

import pytest

from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryErrorCode,
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
    derive_geometry_dimensions,
)
from document_intake.domain.value_objects import EntityId


def eid():
    return EntityId(uuid4())


def q():
    return SourceQuadrilateral(
        GeometryPoint(0, 0), GeometryPoint(10, 0), GeometryPoint(10, 6), GeometryPoint(0, 6)
    )


def test_enums_and_recipe_repr_safe():
    recipe = ImageGeometryRecipe(
        eid(),
        eid(),
        None,
        1,
        GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
        10,
        6,
        GeometryQuarterTurn.DEG_90,
        q(),
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        datetime(2026, 7, 23, tzinfo=UTC),
    )
    assert "ImageGeometryRecipe" in repr(recipe)
    assert derive_geometry_dimensions(q(), GeometryQuarterTurn.DEG_90) == (6, 10)
    assert [int(v) for v in GeometryQuarterTurn] == [0, 90, 180, 270]


@pytest.mark.parametrize(
    "quad,code",
    [
        (
            SourceQuadrilateral(
                GeometryPoint(0, 0),
                GeometryPoint(10, 0),
                GeometryPoint(10, 6),
                GeometryPoint(10, 6),
            ),
            GeometryErrorCode.DUPLICATE_POINT,
        ),
        (
            SourceQuadrilateral(
                GeometryPoint(0, 0), GeometryPoint(0, 6), GeometryPoint(10, 6), GeometryPoint(10, 0)
            ),
            GeometryErrorCode.NON_CLOCKWISE_QUADRILATERAL,
        ),
        (
            SourceQuadrilateral(
                GeometryPoint(0, 0), GeometryPoint(1, 0), GeometryPoint(1, 1), GeometryPoint(0, 1)
            ),
            GeometryErrorCode.AREA_TOO_SMALL,
        ),
    ],
)
def test_invalid_quadrilaterals(quad, code):
    with pytest.raises(InvalidValueError, match=code.value):
        quad.validate_for_source(10, 6)


def test_bool_as_int_rejected():
    with pytest.raises(InvalidValueError):
        GeometryPoint(True, 0)
    with pytest.raises(InvalidValueError):
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", True)
