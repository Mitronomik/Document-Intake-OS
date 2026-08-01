from __future__ import annotations

import sqlite3

import pytest

from tests.support.pr011 import entity_id
from tests.support.pr012_persistence import recipe, region_set, schema8_uow, table_rows


@pytest.fixture
def persisted_rows():
    connection, uow = schema8_uow()
    geometry = recipe(100, 20, 100, 1)
    uow.image_geometry_recipes.add(geometry)
    regions = region_set(400, 20, 1, None, ((100, 100),))
    uow.document_region_sets.add(regions)
    connection.commit()
    return connection, geometry, regions


MUTATIONS = (
    (
        "geometry projected update",
        "UPDATE image_geometry_recipes SET source_effective_width=31 WHERE recipe_version_id=?",
        lambda geometry, regions: (str(geometry.recipe_version_id),),
    ),
    (
        "geometry payload update",
        "UPDATE image_geometry_recipes SET canonical_payload='{}' WHERE recipe_version_id=?",
        lambda geometry, regions: (str(geometry.recipe_version_id),),
    ),
    (
        "geometry delete",
        "DELETE FROM image_geometry_recipes WHERE recipe_version_id=?",
        lambda geometry, regions: (str(geometry.recipe_version_id),),
    ),
    (
        "geometry replace",
        "INSERT OR REPLACE INTO image_geometry_recipes "
        "SELECT * FROM image_geometry_recipes WHERE recipe_version_id=?",
        lambda geometry, regions: (str(geometry.recipe_version_id),),
    ),
    (
        "set projected update",
        "UPDATE document_region_set_versions "
        "SET confirmed_at_utc='2026-01-01T00:00:00Z' WHERE region_set_version_id=?",
        lambda geometry, regions: (str(regions.region_set_version_id),),
    ),
    (
        "set payload update",
        "UPDATE document_region_set_versions "
        "SET canonical_payload='{}' WHERE region_set_version_id=?",
        lambda geometry, regions: (str(regions.region_set_version_id),),
    ),
    (
        "set delete",
        "DELETE FROM document_region_set_versions WHERE region_set_version_id=?",
        lambda geometry, regions: (str(regions.region_set_version_id),),
    ),
    (
        "set replace",
        "INSERT OR REPLACE INTO document_region_set_versions "
        "SELECT * FROM document_region_set_versions WHERE region_set_version_id=?",
        lambda geometry, regions: (str(regions.region_set_version_id),),
    ),
    (
        "member order update",
        "UPDATE document_region_set_members SET order_index=2 WHERE region_set_version_id=?",
        lambda geometry, regions: (str(regions.region_set_version_id),),
    ),
    (
        "member region update",
        "UPDATE document_region_set_members SET region_id=? WHERE region_set_version_id=?",
        lambda geometry, regions: (str(entity_id(200)), str(regions.region_set_version_id)),
    ),
    (
        "member recipe update",
        "UPDATE document_region_set_members "
        "SET geometry_recipe_version_id=? WHERE region_set_version_id=?",
        lambda geometry, regions: (str(entity_id(999)), str(regions.region_set_version_id)),
    ),
    (
        "member delete",
        "DELETE FROM document_region_set_members WHERE region_set_version_id=?",
        lambda geometry, regions: (str(regions.region_set_version_id),),
    ),
    (
        "member replace",
        "INSERT OR REPLACE INTO document_region_set_members "
        "SELECT * FROM document_region_set_members WHERE region_set_version_id=?",
        lambda geometry, regions: (str(regions.region_set_version_id),),
    ),
)


@pytest.mark.parametrize(("label", "sql", "parameters"), MUTATIONS)
def test_all_pr012_rows_are_immutable_and_failed_mutations_preserve_state(
    persisted_rows, label, sql, parameters
) -> None:
    del label
    connection, geometry, regions = persisted_rows
    before = {
        table: table_rows(connection, table)
        for table in (
            "image_geometry_recipes",
            "document_region_set_versions",
            "document_region_set_members",
        )
    }
    connection.execute("BEGIN IMMEDIATE")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(sql, parameters(geometry, regions))
    connection.rollback()
    assert {table: table_rows(connection, table) for table in before} == before
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("SELECT 1").fetchone() == (1,)
    assert not connection.in_transaction
