import sqlite3
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

import pytest

from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.persistence import database
from document_intake.persistence import serialization as ser
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.repositories.document_regions import DocumentRegionSetRepo
from document_intake.persistence.repositories.image_geometry import ImageGeometryRecipeRepo
from tests.persistence.test_pr012_migration_acceptance import add_source_and_recipe, schema7
from tests.support.pr011 import STAMP, actor, entity_id, valid_geometry_recipe

PARENT_INSERT = (
    "INSERT INTO document_region_set_versions(region_set_version_id,source_file_id,"
    "superseded_region_set_version_id,revision,confirmed_at_utc,confirmed_by_actor_id,"
    "confirmed_by_actor_kind,canonical_payload) VALUES(?,?,?,?,?,?,?,?)"
)
MEMBER_INSERT = (
    "INSERT INTO document_region_set_members(region_set_version_id,order_index,region_id,"
    "geometry_recipe_version_id) VALUES(?,?,?,?)"
)


@dataclass(frozen=True, slots=True)
class SqlCall:
    sql: str
    parameters: tuple[object, ...]


class RecordingConnection:
    def __init__(self, connection: sqlite3.Connection, *, fail_second_member: bool = False) -> None:
        self.connection = connection
        self.calls: list[SqlCall] = []
        self.fail_second_member = fail_second_member
        self.member_inserts = 0

    @property
    def in_transaction(self) -> bool:
        return self.connection.in_transaction

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
        normalized = " ".join(sql.split())
        self.calls.append(SqlCall(normalized, tuple(parameters)))
        if normalized == MEMBER_INSERT:
            self.member_inserts += 1
            if self.fail_second_member and self.member_inserts == 2:
                raise sqlite3.IntegrityError("synthetic second member constraint")
        return self.connection.execute(sql, parameters)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.connection, name)


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


def recording_uow8(*, fail_second_member: bool = False):
    connection, prerequisite_uow = uow8()
    first = prerequisite_uow.image_geometry_recipes.get(entity_id(30))
    assert first is not None
    second = replace(first, recipe_version_id=entity_id(40), region_id=entity_id(40))
    prerequisite_uow.image_geometry_recipes.add(second)
    connection.commit()
    recording = RecordingConnection(connection, fail_second_member=fail_second_member)
    uow = SimpleNamespace(
        _connection=lambda: recording,
        _invalidate_if_transaction_lost=lambda: None,
        _invalidate=lambda: None,
    )
    uow.image_geometry_recipes = ImageGeometryRecipeRepo(uow)
    uow.document_region_sets = DocumentRegionSetRepo(uow)
    return connection, recording, uow, first, second


def two_member_set(set_number: int, first, second) -> DocumentRegionSetVersion:
    return DocumentRegionSetVersion(
        entity_id(set_number),
        first.source_file_id,
        None,
        1,
        (
            DocumentRegionSetMember(1, second.region_id, second.recipe_version_id),
            DocumentRegionSetMember(2, first.region_id, first.recipe_version_id),
        ),
        STAMP,
        actor(),
    )


def parent_parameters(region_set: DocumentRegionSetVersion) -> tuple[object, ...]:
    return (
        str(region_set.region_set_version_id),
        str(region_set.source_file_id),
        None,
        region_set.revision,
        ser.utc_iso(region_set.confirmed_at),
        str(region_set.confirmed_by.actor_id),
        region_set.confirmed_by.kind.value,
        ser.document_region_set_to_json(region_set),
    )


def member_parameters(
    region_set: DocumentRegionSetVersion, member: DocumentRegionSetMember
) -> tuple[object, ...]:
    return (
        str(region_set.region_set_version_id),
        member.order_index,
        str(member.region_id),
        str(member.geometry_recipe_version_id),
    )


def rows_for_set(connection: sqlite3.Connection, region_set_id) -> tuple[list[Any], list[Any]]:
    parent = connection.execute(
        "SELECT * FROM document_region_set_versions WHERE region_set_version_id=?",
        (str(region_set_id),),
    ).fetchall()
    members = connection.execute(
        "SELECT * FROM document_region_set_members WHERE region_set_version_id=? "
        "ORDER BY order_index",
        (str(region_set_id),),
    ).fetchall()
    return parent, members


def write_calls(recording: RecordingConnection) -> list[SqlCall]:
    start = next(
        index
        for index, call in enumerate(recording.calls)
        if call.sql == "SAVEPOINT repository_write"
    )
    return recording.calls[start:]


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


def test_duplicate_parent_maps_to_entity_already_exists_and_preserves_existing_rows() -> None:
    c, u = uow8()
    recipe = u.image_geometry_recipes.get(entity_id(30))
    assert recipe is not None
    region_set = DocumentRegionSetVersion(
        entity_id(62),
        recipe.source_file_id,
        None,
        1,
        (DocumentRegionSetMember(1, recipe.region_id, recipe.recipe_version_id),),
        STAMP,
        actor(),
    )
    u.document_region_sets.add(region_set)
    c.commit()
    parent_before = c.execute(
        "SELECT * FROM document_region_set_versions WHERE region_set_version_id=?",
        (str(region_set.region_set_version_id),),
    ).fetchall()
    members_before = c.execute(
        "SELECT * FROM document_region_set_members WHERE region_set_version_id=?",
        (str(region_set.region_set_version_id),),
    ).fetchall()

    c.execute("BEGIN IMMEDIATE")
    with pytest.raises(PersistenceError) as caught:
        u.document_region_sets.add(region_set)

    assert caught.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    assert c.in_transaction
    assert c.execute("SELECT 1").fetchone() == (1,)
    parent_after = c.execute(
        "SELECT * FROM document_region_set_versions WHERE region_set_version_id=?",
        (str(region_set.region_set_version_id),),
    ).fetchall()
    members_after = c.execute(
        "SELECT * FROM document_region_set_members WHERE region_set_version_id=?",
        (str(region_set.region_set_version_id),),
    ).fetchall()
    assert parent_after == parent_before
    assert members_after == members_before
    assert len(parent_after) == 1
    assert len(members_after) == 1
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    c.rollback()
    assert u.document_region_sets.get(region_set.region_set_version_id) == region_set


def test_two_member_add_stages_parent_then_members_in_domain_order_without_commit() -> None:
    connection, recording, uow, first, second = recording_uow8()
    region_set = two_member_set(63, first, second)
    assert tuple(str(member.region_id) for member in region_set.members) != tuple(
        sorted(str(member.region_id) for member in region_set.members)
    )
    connection.execute("BEGIN IMMEDIATE")
    recording.calls.clear()

    uow.document_region_sets.add(region_set)

    assert write_calls(recording) == [
        SqlCall("SAVEPOINT repository_write", ()),
        SqlCall(PARENT_INSERT, parent_parameters(region_set)),
        SqlCall(MEMBER_INSERT, member_parameters(region_set, region_set.members[0])),
        SqlCall(MEMBER_INSERT, member_parameters(region_set, region_set.members[1])),
        SqlCall("RELEASE SAVEPOINT repository_write", ()),
    ]
    assert recording.in_transaction
    assert all(call.sql != "COMMIT" for call in recording.calls)
    parent, members = rows_for_set(connection, region_set.region_set_version_id)
    assert len(parent) == 1
    assert members == [
        member_parameters(region_set, region_set.members[0]),
        member_parameters(region_set, region_set.members[1]),
    ]
    assert uow.document_region_sets.get(region_set.region_set_version_id) == region_set
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    connection.rollback()
    assert rows_for_set(connection, region_set.region_set_version_id) == ([], [])
    assert connection.execute("SELECT count(*) FROM source_files").fetchone() == (1,)
    assert connection.execute("SELECT count(*) FROM image_geometry_recipes").fetchone() == (2,)


def test_second_member_failure_rolls_back_parent_and_first_member_without_commit() -> None:
    connection, recording, uow, first, second = recording_uow8(fail_second_member=True)
    invalid = two_member_set(64, first, second)
    connection.execute("BEGIN IMMEDIATE")
    recording.calls.clear()

    with pytest.raises(PersistenceError) as caught:
        uow.document_region_sets.add(invalid)

    assert caught.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    assert write_calls(recording) == [
        SqlCall("SAVEPOINT repository_write", ()),
        SqlCall(PARENT_INSERT, parent_parameters(invalid)),
        SqlCall(MEMBER_INSERT, member_parameters(invalid, invalid.members[0])),
        SqlCall(MEMBER_INSERT, member_parameters(invalid, invalid.members[1])),
        SqlCall("ROLLBACK TO SAVEPOINT repository_write", ()),
        SqlCall("RELEASE SAVEPOINT repository_write", ()),
    ]
    assert rows_for_set(connection, invalid.region_set_version_id) == ([], [])
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert recording.in_transaction
    assert connection.execute("SELECT 1").fetchone() == (1,)
    assert all(call.sql != "COMMIT" for call in recording.calls)

    valid = two_member_set(65, first, second)
    recording.calls.clear()
    uow.document_region_sets.add(valid)
    assert recording.in_transaction
    assert len(rows_for_set(connection, valid.region_set_version_id)[1]) == 2
    assert all(call.sql != "COMMIT" for call in recording.calls)
    connection.rollback()
    assert rows_for_set(connection, valid.region_set_version_id) == ([], [])
    assert connection.execute("SELECT count(*) FROM image_geometry_recipes").fetchone() == (2,)


def test_duplicate_parent_failure_attempts_no_memberships_and_preserves_outer_transaction() -> None:
    connection, recording, uow, first, second = recording_uow8()
    region_set = two_member_set(66, first, second)
    uow.document_region_sets.add(region_set)
    connection.commit()
    parent_before, members_before = rows_for_set(connection, region_set.region_set_version_id)
    connection.execute("BEGIN IMMEDIATE")
    recording.calls.clear()

    with pytest.raises(PersistenceError) as caught:
        uow.document_region_sets.add(region_set)

    assert caught.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    assert write_calls(recording) == [
        SqlCall("SAVEPOINT repository_write", ()),
        SqlCall(PARENT_INSERT, parent_parameters(region_set)),
        SqlCall("ROLLBACK TO SAVEPOINT repository_write", ()),
        SqlCall("RELEASE SAVEPOINT repository_write", ()),
    ]
    assert not any(call.sql == MEMBER_INSERT for call in recording.calls)
    assert all(call.sql != "COMMIT" for call in recording.calls)
    assert rows_for_set(connection, region_set.region_set_version_id) == (
        parent_before,
        members_before,
    )
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert recording.in_transaction
    assert connection.execute("SELECT 1").fetchone() == (1,)
    connection.rollback()
    assert uow.document_region_sets.get(region_set.region_set_version_id) == region_set
