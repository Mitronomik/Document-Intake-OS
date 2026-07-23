from datetime import UTC, datetime
from uuid import uuid4

import pytest

from document_intake.application.dto.image_geometry import CreateImageGeometryRecipeCommand
from document_intake.application.services.image_geometry import (
    ImageGeometryError,
    create_image_geometry_recipe,
)
from document_intake.domain.enums import ActorKind
from document_intake.domain.image_geometry import (
    GeometryErrorCode,
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    SourceQuadrilateral,
)
from document_intake.domain.value_objects import ActorRef, EntityId


def eid():
    return EntityId(uuid4())


def cmd():
    return CreateImageGeometryRecipeCommand(
        eid(),
        eid(),
        None,
        1,
        10,
        10,
        SourceQuadrilateral(
            GeometryPoint(0, 0), GeometryPoint(10, 0), GeometryPoint(10, 10), GeometryPoint(0, 10)
        ),
        GeometryQuarterTurn.DEG_0,
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        datetime(2026, 7, 23, tzinfo=UTC),
        ActorRef(eid(), ActorKind.OPERATOR),
        eid(),
        eid(),
    )


def test_pipeline_validation_before_uow():
    c = cmd()
    c = CreateImageGeometryRecipeCommand(
        c.recipe_version_id,
        c.source_file_id,
        c.superseded_recipe_version_id,
        c.revision,
        c.expected_source_effective_width,
        c.expected_source_effective_height,
        SourceQuadrilateral(
            GeometryPoint(0, 0), GeometryPoint(1, 0), GeometryPoint(1, 1), GeometryPoint(0, 1)
        ),
        c.quarter_turn,
        c.pipeline,
        c.created_at,
        c.actor,
        c.audit_event_id,
        c.correlation_id,
    )

    class F:
        def unit_of_work(self):
            raise AssertionError("uow used")

    with pytest.raises(ImageGeometryError) as e:
        create_image_geometry_recipe(
            c, decoder=object(), renderer=object(), storage=object(), unit_of_work_factory=F()
        )
    assert e.value.code is GeometryErrorCode.AREA_TOO_SMALL
