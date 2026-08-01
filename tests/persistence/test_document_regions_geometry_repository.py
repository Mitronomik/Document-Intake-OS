from __future__ import annotations

import pytest

from document_intake.persistence import serialization as ser
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import entity_id
from tests.support.pr012_persistence import recipe, schema8_uow

INSERT = (
    "INSERT INTO image_geometry_recipes(recipe_version_id,source_file_id,region_id,"
    "superseded_recipe_version_id,revision,coordinate_space,source_effective_width,"
    "source_effective_height,quarter_turn_clockwise,top_left_x,top_left_y,top_right_x,"
    "top_right_y,bottom_right_x,bottom_right_y,bottom_left_x,bottom_left_y,"
    "geometry_pipeline_id,geometry_pipeline_version,created_at_utc,canonical_payload) "
    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


def insert_raw(connection, value, *, columns=None, payload=None) -> None:
    connection.execute(
        INSERT,
        (
            *(ser.image_geometry_recipe_columns(value) if columns is None else columns),
            ser.image_geometry_recipe_to_json(value) if payload is None else payload,
        ),
    )


def assert_invalid(operation) -> None:
    with pytest.raises(PersistenceError) as caught:
        operation()
    assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_independent_same_source_lineages_exact_scoped_history_and_read_purity() -> None:
    connection, uow = schema8_uow()
    a1 = recipe(100, 20, 100, 1, offset=0)
    a2 = recipe(101, 20, 100, 2, 100, offset=1)
    b1 = recipe(200, 20, 200, 1, offset=8)
    b2 = recipe(201, 20, 200, 2, 200, offset=9)
    for item in (a1, a2, b1, b2):
        uow.image_geometry_recipes.add(item)
    connection.commit()
    before = tuple(connection.execute("SELECT * FROM image_geometry_recipes ORDER BY rowid"))

    assert a1.recipe_version_id == a1.region_id
    assert a2.recipe_version_id != a2.region_id
    assert b1.recipe_version_id == b1.region_id
    assert b2.recipe_version_id != b2.region_id
    assert a2.superseded_recipe_version_id == a1.recipe_version_id
    assert b2.superseded_recipe_version_id == b1.recipe_version_id
    for expected in (a1, a2, b1, b2):
        assert uow.image_geometry_recipes.get(expected.recipe_version_id) == expected
    assert uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(100)) == (a1, a2)
    assert uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(200)) == (b1, b2)
    assert uow.image_geometry_recipes.get_latest_by_region(entity_id(20), entity_id(100)) == a2
    assert uow.image_geometry_recipes.get_latest_by_region(entity_id(20), entity_id(200)) == b2
    assert uow.image_geometry_recipes.list_by_source(entity_id(20)) == (a1, a2, b1, b2)
    assert (
        tuple(connection.execute("SELECT * FROM image_geometry_recipes ORDER BY rowid")) == before
    )
    assert not connection.in_transaction


def test_source_scopes_are_isolated_with_equal_revision_numbers() -> None:
    connection, uow = schema8_uow(second_source=True)
    a = (recipe(100, 20, 100, 1), recipe(101, 20, 100, 2, 100, offset=1))
    b = (recipe(300, 21, 300, 1), recipe(301, 21, 300, 2, 300, offset=1))
    for item in (*a, *b):
        uow.image_geometry_recipes.add(item)
    connection.commit()
    assert uow.image_geometry_recipes.list_by_source(entity_id(20)) == a
    assert uow.image_geometry_recipes.list_by_source(entity_id(21)) == b
    assert tuple(item.revision for item in (*a, *b)) == (1, 2, 1, 2)


def test_repository_add_rejects_cross_region_supersession() -> None:
    connection, uow = schema8_uow()
    a1 = recipe(100, 20, 100, 1)
    b1 = recipe(200, 20, 200, 1, offset=8)
    uow.image_geometry_recipes.add(a1)
    uow.image_geometry_recipes.add(b1)
    connection.commit()
    wrong = recipe(201, 20, 200, 2, 100, offset=9)
    with pytest.raises(PersistenceError) as caught:
        uow.image_geometry_recipes.add(wrong)
    assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
    assert uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(100)) == (a1,)
    assert uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(200)) == (b1,)


def test_raw_cross_region_predecessor_fails_only_requested_region() -> None:
    connection, uow = schema8_uow()
    a1 = recipe(100, 20, 100, 1)
    b1 = recipe(200, 20, 200, 1, offset=8)
    uow.image_geometry_recipes.add(a1)
    uow.image_geometry_recipes.add(b1)
    insert_raw(connection, recipe(201, 20, 200, 2, 100, offset=9))
    connection.commit()
    assert uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(100)) == (a1,)
    assert_invalid(lambda: uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(200)))
    assert_invalid(lambda: uow.image_geometry_recipes.list_by_source(entity_id(20)))
    assert_invalid(uow.image_geometry_recipes.validate_all)


def test_revision_gap_fails_closed() -> None:
    connection, uow = schema8_uow()
    uow.image_geometry_recipes.add(recipe(100, 20, 100, 1))
    insert_raw(connection, recipe(102, 20, 100, 3, 100, offset=2))
    connection.commit()
    assert_invalid(lambda: uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(100)))


def test_non_immediate_predecessor_branch_is_rejected_by_schema() -> None:
    _connection, uow = schema8_uow()
    uow.image_geometry_recipes.add(recipe(100, 20, 100, 1))
    uow.image_geometry_recipes.add(recipe(101, 20, 100, 2, 100, offset=1))
    branch = recipe(102, 20, 100, 3, 100, offset=2)
    with pytest.raises(PersistenceError) as caught:
        uow.image_geometry_recipes._execute(
            INSERT,
            (*ser.image_geometry_recipe_columns(branch), ser.image_geometry_recipe_to_json(branch)),
        )
    assert caught.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT


@pytest.mark.parametrize(
    ("column_index", "invalid_value"),
    [(5, "UNSUPPORTED_COORDINATES"), (17, "UNSUPPORTED_PIPELINE")],
)
def test_schema_rejects_unrepresentable_coordinate_or_pipeline_change(
    column_index: int, invalid_value: str
) -> None:
    _connection, uow = schema8_uow()
    root = recipe(100, 20, 100, 1)
    uow.image_geometry_recipes.add(root)
    later = recipe(101, 20, 100, 2, 100, offset=1)
    columns = list(ser.image_geometry_recipe_columns(later))
    columns[column_index] = invalid_value
    with pytest.raises(PersistenceError) as caught:
        uow.image_geometry_recipes._execute(
            INSERT,
            (*columns, ser.image_geometry_recipe_to_json(later)),
        )
    assert caught.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT


def test_schema_rejects_unrepresentable_wrong_root_identity() -> None:
    _connection, uow = schema8_uow()
    root = recipe(100, 20, 100, 1)
    columns = list(ser.image_geometry_recipe_columns(root))
    columns[2] = str(entity_id(200))
    with pytest.raises(PersistenceError) as caught:
        uow.image_geometry_recipes._execute(
            INSERT,
            (*columns, ser.image_geometry_recipe_to_json(root)),
        )
    assert caught.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT


@pytest.mark.parametrize(
    "mismatch", ["projection", "payload", "source", "region", "revision", "predecessor"]
)
def test_canonical_payload_and_projection_mismatches_fail_closed(mismatch: str) -> None:
    connection, uow = schema8_uow(second_source=True)
    stored = recipe(100, 20, 100, 1)
    columns = list(ser.image_geometry_recipe_columns(stored))
    payload = ser.image_geometry_recipe_to_json(stored)
    if mismatch == "projection":
        columns[19] = "2026-07-27T00:00:00Z"
    elif mismatch == "payload":
        payload = "{}"
    elif mismatch == "source":
        payload = ser.image_geometry_recipe_to_json(recipe(100, 21, 100, 1))
    elif mismatch == "region":
        payload = ser.image_geometry_recipe_to_json(recipe(200, 20, 200, 1, offset=8))
    elif mismatch == "revision":
        payload = ser.image_geometry_recipe_to_json(recipe(101, 20, 100, 2, 100, offset=1))
    else:
        payload = ser.image_geometry_recipe_to_json(recipe(101, 20, 100, 2, 999, offset=1))
    insert_raw(connection, stored, columns=columns, payload=payload)
    connection.commit()
    assert_invalid(lambda: uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(100)))


def test_corruption_outside_region_and_source_does_not_poison_scoped_reads() -> None:
    connection, uow = schema8_uow(second_source=True)
    a = recipe(100, 20, 100, 1)
    b = recipe(200, 20, 200, 1, offset=8)
    other = recipe(300, 21, 300, 1)
    uow.image_geometry_recipes.add(a)
    insert_raw(connection, b, payload="{}")
    insert_raw(connection, other, payload="{}")
    connection.commit()
    before = tuple(connection.execute("SELECT * FROM image_geometry_recipes ORDER BY rowid"))
    assert uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(100)) == (a,)
    assert_invalid(lambda: uow.image_geometry_recipes.list_by_region(entity_id(20), entity_id(200)))
    assert_invalid(lambda: uow.image_geometry_recipes.list_by_source(entity_id(20)))
    assert_invalid(uow.image_geometry_recipes.validate_all)
    assert (
        tuple(connection.execute("SELECT * FROM image_geometry_recipes ORDER BY rowid")) == before
    )
    assert not connection.in_transaction


def test_corruption_in_another_source_does_not_poison_source_scoped_read() -> None:
    connection, uow = schema8_uow(second_source=True)
    source_a = recipe(100, 20, 100, 1)
    source_b = recipe(300, 21, 300, 1)
    uow.image_geometry_recipes.add(source_a)
    insert_raw(connection, source_b, payload="{}")
    connection.commit()
    before = tuple(connection.execute("SELECT * FROM image_geometry_recipes ORDER BY rowid"))
    assert uow.image_geometry_recipes.list_by_source(entity_id(20)) == (source_a,)
    assert_invalid(lambda: uow.image_geometry_recipes.list_by_source(entity_id(21)))
    assert (
        tuple(connection.execute("SELECT * FROM image_geometry_recipes ORDER BY rowid")) == before
    )
    assert not connection.in_transaction
