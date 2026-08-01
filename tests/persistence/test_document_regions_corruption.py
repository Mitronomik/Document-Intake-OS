from __future__ import annotations

import pytest

from document_intake.persistence import serialization as ser
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import entity_id
from tests.support.pr012_persistence import recipe, region_set, schema8_uow

PARENT_INSERT = (
    "INSERT INTO document_region_set_versions(region_set_version_id,source_file_id,"
    "superseded_region_set_version_id,revision,confirmed_at_utc,confirmed_by_actor_id,"
    "confirmed_by_actor_kind,canonical_payload) VALUES(?,?,?,?,?,?,?,?)"
)
MEMBER_INSERT = (
    "INSERT INTO document_region_set_members(region_set_version_id,order_index,region_id,"
    "geometry_recipe_version_id) VALUES(?,?,?,?)"
)


def parent_parameters(value, *, overrides=None, payload=None):
    parameters = [
        str(value.region_set_version_id),
        str(value.source_file_id),
        None
        if value.superseded_region_set_version_id is None
        else str(value.superseded_region_set_version_id),
        value.revision,
        ser.utc_iso(value.confirmed_at),
        str(value.confirmed_by.actor_id),
        value.confirmed_by.kind.value,
        ser.document_region_set_to_json(value) if payload is None else payload,
    ]
    for index, replacement in overrides or ():
        parameters[index] = replacement
    return tuple(parameters)


def insert_set_raw(connection, value, *, overrides=None, payload=None, members=True) -> None:
    connection.execute(
        PARENT_INSERT, parent_parameters(value, overrides=overrides, payload=payload)
    )
    if members:
        for member in value.members:
            connection.execute(
                MEMBER_INSERT,
                (
                    str(value.region_set_version_id),
                    member.order_index,
                    str(member.region_id),
                    str(member.geometry_recipe_version_id),
                ),
            )


def assert_invalid(operation) -> None:
    with pytest.raises(PersistenceError) as caught:
        operation()
    assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


@pytest.mark.parametrize("kind", ["revision_gap", "cross_source"])
def test_representable_set_chain_corruption_fails_closed(kind: str) -> None:
    connection, uow = schema8_uow(second_source=kind == "cross_source")
    root_recipe = recipe(100, 20, 100, 1)
    uow.image_geometry_recipes.add(root_recipe)
    first = region_set(400, 20, 1, None, ((100, 100),))
    uow.document_region_sets.add(first)
    if kind == "revision_gap":
        corrupt = region_set(402, 20, 3, 400, ((100, 100),))
    else:
        other_recipe = recipe(300, 21, 300, 1)
        uow.image_geometry_recipes.add(other_recipe)
        corrupt = region_set(500, 21, 1, None, ((300, 300),))
        insert_set_raw(connection, corrupt, overrides=((2, str(first.region_set_version_id)),))
        connection.commit()
        assert uow.document_region_sets.list_by_source(entity_id(20)) == (first,)
        assert_invalid(lambda: uow.document_region_sets.list_by_source(entity_id(21)))
        return
    insert_set_raw(connection, corrupt)
    connection.commit()
    assert_invalid(lambda: uow.document_region_sets.list_by_source(entity_id(20)))


@pytest.mark.parametrize("mismatch", ["predecessor", "revision", "source"])
def test_set_payload_projection_mismatch_fails_closed(mismatch: str) -> None:
    connection, uow = schema8_uow(second_source=mismatch == "source")
    root = recipe(100, 20, 100, 1)
    uow.image_geometry_recipes.add(root)
    stored = region_set(400, 20, 1, None, ((100, 100),))
    if mismatch in {"predecessor", "revision"}:
        payload_value = region_set(401, 20, 2, 400, ((100, 100),))
    else:
        other = recipe(300, 21, 300, 1)
        uow.image_geometry_recipes.add(other)
        payload_value = region_set(500, 21, 1, None, ((300, 300),))
    insert_set_raw(
        connection,
        stored,
        payload=ser.document_region_set_to_json(payload_value),
    )
    connection.commit()
    assert_invalid(lambda: uow.document_region_sets.list_by_source(entity_id(20)))


@pytest.mark.parametrize("kind", ["missing", "extra", "order", "payload_members"])
def test_member_sql_and_payload_mismatch_fails_closed(kind: str) -> None:
    connection, uow = schema8_uow()
    a = recipe(100, 20, 100, 1)
    b = recipe(200, 20, 200, 1, offset=8)
    uow.image_geometry_recipes.add(a)
    uow.image_geometry_recipes.add(b)
    value = region_set(400, 20, 1, None, ((100, 100), (200, 200)))
    if kind == "missing":
        insert_set_raw(connection, value, members=False)
        connection.execute(
            MEMBER_INSERT, (str(entity_id(400)), 1, str(entity_id(100)), str(entity_id(100)))
        )
    elif kind == "extra":
        one = region_set(400, 20, 1, None, ((100, 100),))
        insert_set_raw(connection, one)
        connection.execute(
            MEMBER_INSERT, (str(entity_id(400)), 2, str(entity_id(200)), str(entity_id(200)))
        )
    elif kind == "order":
        insert_set_raw(connection, value, members=False)
        connection.execute(
            MEMBER_INSERT, (str(entity_id(400)), 1, str(entity_id(200)), str(entity_id(200)))
        )
        connection.execute(
            MEMBER_INSERT, (str(entity_id(400)), 2, str(entity_id(100)), str(entity_id(100)))
        )
    else:
        insert_set_raw(
            connection,
            value,
            payload=ser.document_region_set_to_json(
                region_set(400, 20, 1, None, ((200, 200), (100, 100)))
            ),
        )
    connection.commit()
    assert_invalid(lambda: uow.document_region_sets.get(entity_id(400)))


@pytest.mark.parametrize("kind", ["other_source", "other_region"])
def test_repository_add_rejects_member_recipe_identity_mismatch(kind: str) -> None:
    connection, uow = schema8_uow(second_source=kind == "other_source")
    if kind == "other_source":
        wrong_recipe = recipe(300, 21, 300, 1)
        member = ((300, 300),)
        source_id = 20
    else:
        wrong_recipe = recipe(200, 20, 200, 1, offset=8)
        member = ((100, 200),)
        source_id = 20
    uow.image_geometry_recipes.add(wrong_recipe)
    connection.commit()
    invalid = region_set(400, source_id, 1, None, member)
    with pytest.raises(PersistenceError) as caught:
        uow.document_region_sets.add(invalid)
    assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
    assert connection.execute("SELECT count(*) FROM document_region_set_versions").fetchone() == (
        0,
    )


@pytest.mark.parametrize("kind", ["other_source", "other_region"])
def test_raw_member_recipe_identity_mismatch_fails_closed(kind: str) -> None:
    connection, uow = schema8_uow(second_source=kind == "other_source")
    if kind == "other_source":
        wrong_recipe = recipe(300, 21, 300, 1)
        invalid = region_set(400, 20, 1, None, ((300, 300),))
    else:
        wrong_recipe = recipe(200, 20, 200, 1, offset=8)
        invalid = region_set(400, 20, 1, None, ((100, 200),))
    uow.image_geometry_recipes.add(wrong_recipe)
    insert_set_raw(connection, invalid)
    connection.commit()
    before = (
        tuple(connection.execute("SELECT * FROM document_region_set_versions ORDER BY rowid")),
        tuple(connection.execute("SELECT * FROM document_region_set_members ORDER BY rowid")),
    )
    assert_invalid(lambda: uow.document_region_sets.get(entity_id(400)))
    after = (
        tuple(connection.execute("SELECT * FROM document_region_set_versions ORDER BY rowid")),
        tuple(connection.execute("SELECT * FROM document_region_set_members ORDER BY rowid")),
    )
    assert after == before
    assert not connection.in_transaction


def test_corrupt_other_source_does_not_poison_valid_source_history() -> None:
    connection, uow = schema8_uow(second_source=True)
    a = recipe(100, 20, 100, 1)
    b = recipe(300, 21, 300, 1)
    uow.image_geometry_recipes.add(a)
    uow.image_geometry_recipes.add(b)
    valid = region_set(400, 20, 1, None, ((100, 100),))
    uow.document_region_sets.add(valid)
    corrupt = region_set(500, 21, 1, None, ((300, 300),))
    insert_set_raw(connection, corrupt, payload="{}")
    connection.commit()
    before = (
        tuple(connection.execute("SELECT * FROM document_region_set_versions ORDER BY rowid")),
        tuple(connection.execute("SELECT * FROM document_region_set_members ORDER BY rowid")),
    )
    assert uow.document_region_sets.list_by_source(entity_id(20)) == (valid,)
    assert_invalid(lambda: uow.document_region_sets.list_by_source(entity_id(21)))
    after = (
        tuple(connection.execute("SELECT * FROM document_region_set_versions ORDER BY rowid")),
        tuple(connection.execute("SELECT * FROM document_region_set_members ORDER BY rowid")),
    )
    assert after == before
    assert not connection.in_transaction


@pytest.mark.parametrize(
    ("case", "parameters"),
    [
        (
            "duplicate_order",
            lambda: (str(entity_id(400)), 1, str(entity_id(200)), str(entity_id(200))),
        ),
        (
            "duplicate_region",
            lambda: (str(entity_id(400)), 2, str(entity_id(100)), str(entity_id(200))),
        ),
        (
            "duplicate_recipe",
            lambda: (str(entity_id(400)), 2, str(entity_id(200)), str(entity_id(100))),
        ),
        (
            "invalid_order",
            lambda: (str(entity_id(400)), 3, str(entity_id(200)), str(entity_id(200))),
        ),
        ("missing_set", lambda: (str(entity_id(999)), 1, str(entity_id(200)), str(entity_id(200)))),
        (
            "missing_recipe",
            lambda: (str(entity_id(400)), 2, str(entity_id(200)), str(entity_id(999))),
        ),
    ],
)
def test_membership_constraints_map_to_persistence_constraint(case, parameters) -> None:
    del case
    connection, uow = schema8_uow()
    a = recipe(100, 20, 100, 1)
    b = recipe(200, 20, 200, 1, offset=8)
    uow.image_geometry_recipes.add(a)
    uow.image_geometry_recipes.add(b)
    first = region_set(400, 20, 1, None, ((100, 100),))
    uow.document_region_sets.add(first)
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    with pytest.raises(PersistenceError) as caught:
        uow.document_region_sets._execute(MEMBER_INSERT, parameters())
    assert caught.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    connection.rollback()
    assert uow.document_region_sets.get(entity_id(400)) == first


def test_duplicate_parent_is_entity_exists_and_branch_or_missing_predecessor_are_constraints() -> (
    None
):
    connection, uow = schema8_uow()
    root = recipe(100, 20, 100, 1)
    uow.image_geometry_recipes.add(root)
    first = region_set(400, 20, 1, None, ((100, 100),))
    second = region_set(401, 20, 2, 400, ((100, 100),))
    uow.document_region_sets.add(first)
    uow.document_region_sets.add(second)
    connection.commit()
    with pytest.raises(PersistenceError) as duplicate:
        uow.document_region_sets.add(first)
    assert duplicate.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    branch = region_set(402, 20, 3, 400, ((100, 100),))
    missing = region_set(403, 20, 3, 999, ((100, 100),))
    for value in (branch, missing):
        with pytest.raises(PersistenceError) as caught:
            uow.document_region_sets._execute(PARENT_INSERT, parent_parameters(value))
        assert caught.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
