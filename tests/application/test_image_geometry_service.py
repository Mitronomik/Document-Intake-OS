from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from tests.support.pr011 import valid_geometry_recipe

from document_intake.application.dto.image_geometry import CreateImageGeometryRecipeCommand
from document_intake.application.services.image_geometry import (
    ImageGeometryError,
    _resolve_predecessor,
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


def test_source_dependent_geometry_validation_waits_for_uow():
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
    assert e.value.code is GeometryErrorCode.RECIPE_PERSISTENCE_FAILED


class RecipeRepo:
    def __init__(self, recipes):
        self.recipes = tuple(recipes)

    def list_by_source(self, source):
        return tuple(r for r in self.recipes if r.source_file_id == source)

    def get(self, recipe_id):
        return next((r for r in self.recipes if r.recipe_version_id == recipe_id), None)

    def get_latest_by_region(self, source, region):
        scoped = [r for r in self.recipes if r.source_file_id == source and r.region_id == region]
        return max(scoped, key=lambda r: r.revision) if scoped else None


class RecipeUow:
    def __init__(self, recipes):
        self.image_geometry_recipes = RecipeRepo(recipes)


def revision_command(predecessor, revision=2):
    value = cmd()
    return replace(
        value,
        source_file_id=predecessor.source_file_id,
        superseded_recipe_version_id=predecessor.recipe_version_id,
        revision=revision,
    )


def test_legacy_first_recipe_requires_empty_source() -> None:
    value = cmd()
    assert _resolve_predecessor(value, RecipeUow(())) is None
    with pytest.raises(ImageGeometryError):
        _resolve_predecessor(
            value,
            RecipeUow((replace(valid_geometry_recipe(), source_file_id=value.source_file_id),)),
        )


def test_exact_predecessor_preserves_single_lineage() -> None:
    root = valid_geometry_recipe()
    assert _resolve_predecessor(revision_command(root), RecipeUow((root,))) == root


def test_second_region_does_not_redirect_revision() -> None:
    root = valid_geometry_recipe()
    other_id = eid()
    other = replace(root, recipe_version_id=other_id, region_id=other_id)
    assert _resolve_predecessor(revision_command(root), RecipeUow((root, other))) == root


def test_outdated_predecessor_is_rejected() -> None:
    root = valid_geometry_recipe()
    latest = replace(
        root,
        recipe_version_id=eid(),
        revision=2,
        superseded_recipe_version_id=root.recipe_version_id,
    )
    with pytest.raises(ImageGeometryError):
        _resolve_predecessor(revision_command(root), RecipeUow((root, latest)))


def test_cross_source_predecessor_is_rejected() -> None:
    root = valid_geometry_recipe()
    value = replace(revision_command(root), source_file_id=eid())
    with pytest.raises(ImageGeometryError):
        _resolve_predecessor(value, RecipeUow((root,)))
