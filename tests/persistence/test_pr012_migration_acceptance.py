import json
import sqlite3

import pytest

from document_intake.domain.value_objects import EntityId
from document_intake.persistence import database, geometry_serialization
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import MIGRATIONS
from tests.persistence.test_migrations import insert_artifact, insert_batch, source_values
from tests.support.pr011 import entity_id, valid_geometry_recipe


def schema7() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:", isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    for migration in MIGRATIONS[:7]:
        database._apply_one_migration(c, migration)
    return c


def add_source_and_recipe(c: sqlite3.Connection, payload_change=None) -> str:
    insert_batch(c)
    insert_artifact(c)
    c.execute(
        "INSERT INTO source_files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", source_values()
    )
    recipe = valid_geometry_recipe()
    recipe = recipe.__class__(
        recipe.recipe_version_id,
        EntityId.parse(source_values()[0]),
        recipe.superseded_recipe_version_id,
        recipe.revision,
        recipe.coordinate_space,
        recipe.source_effective_width,
        recipe.source_effective_height,
        recipe.quarter_turn,
        recipe.quadrilateral,
        recipe.pipeline,
        recipe.created_at,
        recipe.region_id,
    )
    columns = geometry_serialization.image_geometry_recipe_columns(recipe)
    legacy = (columns[0], columns[1], *columns[3:])
    payload = json.loads(geometry_serialization.image_geometry_recipe_to_json(recipe))
    payload.pop("region_id")
    if payload_change:
        payload_change(payload)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    c.execute(
        "INSERT INTO image_geometry_recipes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*legacy, raw),
    )
    return raw


def assert_v0008_rolled_back(
    c: sqlite3.Connection, original_geometry: tuple[tuple[object, ...], ...]
) -> None:
    assert c.execute("PRAGMA user_version").fetchone() == (7,)
    assert c.execute("SELECT 1 FROM schema_migrations WHERE version=8").fetchone() is None
    assert c.execute(
        "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
    ).fetchall() == [(m.version, m.name, m.checksum) for m in MIGRATIONS[:7]]
    assert tuple(c.execute("SELECT * FROM image_geometry_recipes ORDER BY revision")) == (
        original_geometry
    )
    names = {row[0] for row in c.execute("SELECT name FROM sqlite_master")}
    assert "document_region_set_versions" not in names
    assert "document_region_set_members" not in names
    assert "image_geometry_recipes_v0008_new" not in names
    assert not {name for name in names if "v0008" in name}
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_empty_and_populated_schema7_migrate_deterministically() -> None:
    empty = schema7()
    database._apply_one_migration(empty, MIGRATIONS[7])
    assert empty.execute("PRAGMA user_version").fetchone() == (8,)
    populated = schema7()
    old = add_source_and_recipe(populated)
    database._apply_one_migration(populated, MIGRATIONS[7])
    row = populated.execute(
        "SELECT recipe_version_id,region_id,canonical_payload FROM image_geometry_recipes"
    ).fetchone()
    assert row[0] == row[1] and row[2] != old and "region_id" in row[2]
    assert populated.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda p: p.pop("pipeline"), id="missing-field"),
        pytest.param(lambda p: p.__setitem__("unexpected", True), id="extra-field"),
        pytest.param(lambda p: p.__setitem__("revision", 2), id="revision-mismatch"),
        pytest.param(
            lambda p: p.__setitem__("source_file_id", str(entity_id(99))),
            id="source-mismatch",
        ),
        pytest.param(
            lambda p: p.__setitem__("coordinate_space", "UNSUPPORTED"),
            id="invalid-enum",
        ),
        pytest.param(lambda p: p.__setitem__("created_at", "not-a-time"), id="invalid-time"),
        pytest.param(
            lambda p: p["pipeline"].__setitem__("version", 2),
            id="invalid-pipeline",
        ),
        pytest.param(
            lambda p: p.__setitem__("source_effective_width", None),
            id="required-null",
        ),
    ],
)
def test_invalid_legacy_payload_rolls_back(change) -> None:
    c = schema7()
    add_source_and_recipe(c, change)
    original = tuple(c.execute("SELECT * FROM image_geometry_recipes ORDER BY revision"))
    with pytest.raises(PersistenceError) as error:
        database._apply_one_migration(c, MIGRATIONS[7])
    assert error.value.code is PersistenceErrorCode.MIGRATION_FAILED
    assert_v0008_rolled_back(c, original)


def test_malformed_legacy_json_fully_rolls_back() -> None:
    c = schema7()
    add_source_and_recipe(c)
    c.execute("DROP TRIGGER image_geometry_recipes_no_update")
    c.execute("UPDATE image_geometry_recipes SET canonical_payload='{'")
    original = tuple(c.execute("SELECT * FROM image_geometry_recipes ORDER BY revision"))
    with pytest.raises(PersistenceError) as error:
        database._apply_one_migration(c, MIGRATIONS[7])
    assert error.value.code is PersistenceErrorCode.MIGRATION_FAILED
    assert_v0008_rolled_back(c, original)


def test_historical_checksums_are_unchanged() -> None:
    assert [m.checksum for m in MIGRATIONS[:7]] == [
        "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500",
        "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d",
        "e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1",
        "a826d5bc07ba73e6d54fd25e9df8afb42028261040b7981bdd157caf26b1f7c6",
        "6d020d1acfbce3fcb7168e935617f2ae008a32bea7def1f37de84e36e9e2224f",
        "ac9d5bfbe79160d880f30af6ee1ed645ab500b9be140a18b9d6498cc68eba5ec",
        "afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7",
    ]
