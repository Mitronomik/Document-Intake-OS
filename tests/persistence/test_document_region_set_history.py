from __future__ import annotations

from document_intake.persistence import serialization as ser
from tests.support.pr011 import entity_id
from tests.support.pr012_persistence import recipe, region_set, schema8_uow


def test_three_version_history_preserves_exact_members_and_latest() -> None:
    connection, uow = schema8_uow()
    a1 = recipe(100, 20, 100, 1)
    b1 = recipe(200, 20, 200, 1, offset=8)
    b2 = recipe(201, 20, 200, 2, 200, offset=9)
    for item in (a1, b1, b2):
        uow.image_geometry_recipes.add(item)
    versions = (
        region_set(400, 20, 1, None, ((100, 100),)),
        region_set(401, 20, 2, 400, ((100, 100), (200, 200))),
        region_set(402, 20, 3, 401, ((200, 201), (100, 100))),
    )
    for item in versions:
        uow.document_region_sets.add(item)
    connection.commit()
    before = tuple(
        connection.execute(
            "SELECT canonical_payload FROM document_region_set_versions ORDER BY revision"
        )
    )
    for expected in versions:
        assert uow.document_region_sets.get(expected.region_set_version_id) == expected
    assert uow.document_region_sets.list_by_source(entity_id(20)) == versions
    assert uow.document_region_sets.get_latest_by_source(entity_id(20)) == versions[-1]
    assert tuple(item.revision for item in versions) == (1, 2, 3)
    assert tuple(item.superseded_region_set_version_id for item in versions) == (
        None,
        entity_id(400),
        entity_id(401),
    )
    assert tuple(member.order_index for member in versions[2].members) == (1, 2)
    assert tuple(member.region_id for member in versions[2].members) == (
        entity_id(200),
        entity_id(100),
    )
    assert (
        tuple(
            connection.execute(
                "SELECT canonical_payload FROM document_region_set_versions ORDER BY revision"
            )
        )
        == before
    )
    assert tuple(row[0] for row in before) == tuple(
        ser.document_region_set_to_json(item) for item in versions
    )
    assert not connection.in_transaction


def test_separate_source_histories_are_isolated() -> None:
    connection, uow = schema8_uow(second_source=True)
    recipes = (recipe(100, 20, 100, 1), recipe(300, 21, 300, 1))
    for item in recipes:
        uow.image_geometry_recipes.add(item)
    source_a = (
        region_set(400, 20, 1, None, ((100, 100),)),
        region_set(401, 20, 2, 400, ((100, 100),)),
    )
    source_b = (
        region_set(500, 21, 1, None, ((300, 300),)),
        region_set(501, 21, 2, 500, ((300, 300),)),
    )
    for item in (*source_a, *source_b):
        uow.document_region_sets.add(item)
    connection.commit()
    assert uow.document_region_sets.list_by_source(entity_id(20)) == source_a
    assert uow.document_region_sets.list_by_source(entity_id(21)) == source_b
    assert uow.document_region_sets.get_latest_by_source(entity_id(20)) == source_a[-1]
    assert uow.document_region_sets.get_latest_by_source(entity_id(21)) == source_b[-1]
