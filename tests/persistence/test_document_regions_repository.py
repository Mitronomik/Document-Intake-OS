from types import SimpleNamespace

import pytest

from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.persistence import database
from document_intake.persistence.errors import PersistenceError
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.repositories.document_regions import DocumentRegionSetRepo
from document_intake.persistence.repositories.image_geometry import ImageGeometryRecipeRepo
from tests.persistence.test_pr012_migration_acceptance import add_source_and_recipe, schema7
from tests.support.pr011 import STAMP, actor, entity_id, valid_geometry_recipe


def uow8():
    c = schema7()
    add_source_and_recipe(c)
    database._apply_one_migration(c, MIGRATIONS[7])
    u = SimpleNamespace(
        _connection=lambda: c,
        _invalidate_if_transaction_lost=lambda: None,
        _invalidate=lambda: None,
    )
    u.image_geometry_recipes = ImageGeometryRecipeRepo(u)
    u.document_region_sets = DocumentRegionSetRepo(u)
    return c, u


def test_scoped_geometry_and_ordered_historical_set() -> None:
    c, u = uow8()
    recipe = u.image_geometry_recipes.get(entity_id(30))
    assert recipe is not None
    assert (
        u.image_geometry_recipes.get_latest_by_region(recipe.source_file_id, recipe.region_id)
        == recipe
    )
    region_set = DocumentRegionSetVersion(
        entity_id(60),
        recipe.source_file_id,
        None,
        1,
        (DocumentRegionSetMember(1, recipe.region_id, recipe.recipe_version_id),),
        STAMP,
        actor(),
    )
    u.document_region_sets.add(region_set)
    assert u.document_region_sets.list_by_source(recipe.source_file_id) == (region_set,)
    assert c.execute("SELECT order_index FROM document_region_set_members").fetchall() == [(1,)]


def test_parent_member_insert_is_atomic() -> None:
    c, u = uow8()
    recipe = valid_geometry_recipe()
    bad = DocumentRegionSetVersion(
        entity_id(61),
        recipe.source_file_id,
        None,
        1,
        (DocumentRegionSetMember(1, recipe.region_id, entity_id(99)),),
        STAMP,
        actor(),
    )
    with pytest.raises(PersistenceError):
        u.document_region_sets.add(bad)
    assert c.execute("SELECT count(*) FROM document_region_set_versions").fetchone() == (0,)
