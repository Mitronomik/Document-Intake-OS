import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from document_intake.domain.value_objects import EntityId
from document_intake.persistence import database, geometry_serialization, serialization
from document_intake.persistence.database import PreparedImageArtifactRepo
from document_intake.persistence.errors import (
    PersistenceError,
    PersistenceErrorCode,
    translate_driver_error,
)
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.migrations.v0008_document_regions import (
    _validate_legacy_chain,
)
from document_intake.persistence.repositories.image_geometry import ImageGeometryRecipeRepo
from tests.persistence.test_migrations import insert_artifact, insert_batch, source_values
from tests.support.pr011 import entity_id, valid_geometry_recipe
from tests.support.pr012_migration import (
    PREPARED_IDS,
    RECIPE_A_IDS,
    RECIPE_B_IDS,
    SNAPSHOT_TABLES,
    SOURCE_A_ID,
    SOURCE_B_ID,
    DatabaseSnapshot,
    PopulatedSchema7,
    RepositoryUow,
    build_populated_schema7,
    capture_snapshot,
    history,
    schema_object_names,
)


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


def _repositories(
    connection: sqlite3.Connection,
) -> tuple[ImageGeometryRecipeRepo, PreparedImageArtifactRepo]:
    uow = RepositoryUow(connection)
    return ImageGeometryRecipeRepo(uow), PreparedImageArtifactRepo(uow)  # type: ignore[arg-type]


def _natural_lookup(repository: PreparedImageArtifactRepo, artifact):
    return repository.get_by_natural_key(
        artifact.geometry_recipe_version_id,
        artifact.pipeline_id,
        artifact.pipeline_version,
        artifact.output_contract_id,
        artifact.output_contract_version,
    )


def _geometry_rows(connection: sqlite3.Connection) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        connection.execute(
            "SELECT recipe_version_id,source_file_id,region_id,"
            "superseded_recipe_version_id,revision,coordinate_space,"
            "source_effective_width,source_effective_height,quarter_turn_clockwise,"
            "top_left_x,top_left_y,top_right_x,top_right_y,bottom_right_x,"
            "bottom_right_y,bottom_left_x,bottom_left_y,geometry_pipeline_id,"
            "geometry_pipeline_version,created_at_utc,canonical_payload "
            "FROM image_geometry_recipes ORDER BY source_file_id,revision,recipe_version_id"
        ).fetchall()
    )


def test_populated_schema7_fixture_is_exact_before_migration() -> None:
    fixture = build_populated_schema7()
    connection = fixture.connection
    assert connection.execute("PRAGMA user_version").fetchone() == (7,)
    assert history(connection) == [
        (migration.version, migration.name, migration.checksum) for migration in MIGRATIONS[:7]
    ]
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert tuple(
        connection.execute(
            "SELECT id,batch_id,original_artifact_id,original_basename,detected_media_type,"
            "byte_size,sha256,perceptual_algorithm_id,perceptual_algorithm_version,"
            "perceptual_bit_width,perceptual_hex_value,width,height,exif_orientation,"
            "imported_at_utc,imported_by_actor_id,imported_by_actor_kind,canonical_payload "
            "FROM source_files ORDER BY id"
        )
    ) == tuple(
        (*serialization.source_file_columns(source), serialization.source_file_to_json(source))
        for source in fixture.sources
    )
    legacy_rows = tuple(
        connection.execute("SELECT * FROM image_geometry_recipes ORDER BY source_file_id,revision")
    )
    assert tuple(row[:19] for row in legacy_rows) == tuple(
        (
            geometry_serialization.image_geometry_recipe_columns(recipe)[0],
            geometry_serialization.image_geometry_recipe_columns(recipe)[1],
            *geometry_serialization.image_geometry_recipe_columns(recipe)[3:],
        )
        for recipe in fixture.recipes
    )
    assert tuple(row[19] for row in legacy_rows) == tuple(
        payload for _, payload in fixture.legacy_payloads
    )
    assert tuple((row[3], row[2]) for row in legacy_rows) == (
        (1, None),
        (2, str(RECIPE_A_IDS[0])),
        (3, str(RECIPE_A_IDS[1])),
        (1, None),
        (2, str(RECIPE_B_IDS[0])),
    )
    geometry_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(image_geometry_recipes)")
    }
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert "region_id" not in geometry_columns
    assert "document_region_set_versions" not in names
    assert "document_region_set_members" not in names
    assert "image_geometry_recipes_v0008_new" not in names
    assert tuple(table for table, _ in fixture.before.rows) == SNAPSHOT_TABLES

    _geometry_repository, prepared_repository = _repositories(connection)
    for artifact in fixture.prepared:
        assert prepared_repository.get(artifact.id) == artifact
        assert _natural_lookup(prepared_repository, artifact) == artifact
        assert prepared_repository.list_by_geometry_recipe(artifact.geometry_recipe_version_id) == (
            artifact,
        )
    assert prepared_repository.list_by_source(SOURCE_A_ID) == fixture.prepared[:2]
    assert prepared_repository.list_by_source(SOURCE_B_ID) == fixture.prepared[2:]
    assert tuple(artifact.geometry_recipe_version_id for artifact in fixture.prepared) == (
        RECIPE_A_IDS[0],
        RECIPE_A_IDS[2],
        RECIPE_B_IDS[1],
    )


def test_populated_multi_revision_migration_preserves_exact_application_state() -> None:
    fixture = build_populated_schema7()
    connection = fixture.connection
    old_payloads = dict(fixture.legacy_payloads)
    old_recipe_ids = tuple(recipe.recipe_version_id for recipe in fixture.recipes)
    old_prepared_rows = dict(fixture.before.rows)["prepared_image_artifacts"]
    old_stored_rows = dict(fixture.before.rows)["stored_artifacts"]

    database._apply_one_migration(connection, MIGRATIONS[7])

    assert connection.execute("PRAGMA user_version").fetchone() == (8,)
    assert history(connection) == [
        (migration.version, migration.name, migration.checksum) for migration in MIGRATIONS
    ]
    assert MIGRATIONS[7].name == "document_regions_pr012"
    assert (
        MIGRATIONS[7].checksum == "ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b"
    )
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert not connection.in_transaction
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert {
        "document_region_set_versions",
        "document_region_set_members",
        "document_region_sets_source_order_idx",
        "document_region_set_versions_no_update",
        "document_region_set_versions_no_delete",
        "document_region_set_versions_no_replace",
        "document_region_set_members_no_update",
        "document_region_set_members_no_delete",
        "document_region_set_members_no_replace",
        "image_geometry_recipes_source_region_order_idx",
        "image_geometry_recipes_no_update",
        "image_geometry_recipes_no_delete",
        "image_geometry_recipes_no_replace",
    } <= names
    assert "image_geometry_recipes_v0008_new" not in names
    assert "audit_events_v0007" not in names
    assert not {name for name in names if "v0008" in name}
    assert tuple(
        connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE '%image_geometry%' ORDER BY name"
        )
    ) == (("image_geometry_recipes",),)
    assert connection.execute("SELECT count(*) FROM document_region_set_versions").fetchone() == (
        0,
    )
    assert connection.execute("SELECT count(*) FROM document_region_set_members").fetchone() == (0,)

    rows = _geometry_rows(connection)
    assert tuple(EntityId.parse(row[0]) for row in rows) == old_recipe_ids
    assert len(rows) == len(fixture.recipes) == 5
    for row, expected in zip(rows, fixture.recipes, strict=True):
        expected_columns = geometry_serialization.image_geometry_recipe_columns(expected)
        assert tuple(row[:20]) == expected_columns
        assert row[2] == str(expected.region_id)
        assert row[20] != old_payloads[expected.recipe_version_id]
        assert "region_id" in json.loads(row[20])
        assert geometry_serialization.image_geometry_recipe_from_json(row[20]) == expected
        assert geometry_serialization.image_geometry_recipe_to_json(expected) == row[20]
    assert tuple(row[2] for row in rows) == (
        str(RECIPE_A_IDS[0]),
        str(RECIPE_A_IDS[0]),
        str(RECIPE_A_IDS[0]),
        str(RECIPE_B_IDS[0]),
        str(RECIPE_B_IDS[0]),
    )
    assert RECIPE_A_IDS[0] != RECIPE_B_IDS[0]
    assert tuple(row[1] for row in rows[:3]) == (str(SOURCE_A_ID),) * 3
    assert tuple(row[1] for row in rows[3:]) == (str(SOURCE_B_ID),) * 2
    assert tuple(connection.execute("SELECT * FROM prepared_image_artifacts ORDER BY rowid")) == (
        old_prepared_rows
    )
    assert tuple(connection.execute("SELECT * FROM stored_artifacts ORDER BY rowid")) == (
        old_stored_rows
    )

    geometry_repository, prepared_repository = _repositories(connection)
    for expected in fixture.recipes:
        assert geometry_repository.get(expected.recipe_version_id) == expected
    assert (
        geometry_repository.list_by_region(SOURCE_A_ID, RECIPE_A_IDS[0]) == fixture.source_a_recipes
    )
    assert (
        geometry_repository.get_latest_by_region(SOURCE_A_ID, RECIPE_A_IDS[0])
        == fixture.source_a_recipes[-1]
    )
    assert (
        geometry_repository.list_by_region(SOURCE_B_ID, RECIPE_B_IDS[0]) == fixture.source_b_recipes
    )
    assert (
        geometry_repository.get_latest_by_region(SOURCE_B_ID, RECIPE_B_IDS[0])
        == fixture.source_b_recipes[-1]
    )
    assert geometry_repository.list_by_source(SOURCE_A_ID) == fixture.source_a_recipes
    assert geometry_repository.list_by_source(SOURCE_B_ID) == fixture.source_b_recipes
    assert geometry_repository.list_by_region(SOURCE_A_ID, RECIPE_B_IDS[0]) == ()
    assert geometry_repository.list_by_region(SOURCE_B_ID, RECIPE_A_IDS[0]) == ()

    for expected in fixture.prepared:
        assert prepared_repository.get(expected.id) == expected
        assert _natural_lookup(prepared_repository, expected) == expected
        assert prepared_repository.list_by_geometry_recipe(expected.geometry_recipe_version_id) == (
            expected,
        )
    assert prepared_repository.list_by_source(SOURCE_A_ID) == fixture.prepared[:2]
    assert prepared_repository.list_by_source(SOURCE_B_ID) == fixture.prepared[2:]
    assert tuple(item.geometry_recipe_version_id for item in fixture.prepared) == (
        RECIPE_A_IDS[0],
        RECIPE_A_IDS[2],
        RECIPE_B_IDS[1],
    )


def test_file_backed_sqlite_reopen_preserves_exact_migrated_reads(tmp_path: Path) -> None:
    """FILE-BACKED SQLITE REOPEN; this is not encrypted SQLCipher evidence."""
    path = tmp_path / "synthetic-pr012-schema7.db"
    fixture = build_populated_schema7(path)
    database._apply_one_migration(fixture.connection, MIGRATIONS[7])
    fixture.connection.close()

    reopened = sqlite3.connect(path, isolation_level=None)
    reopened.execute("PRAGMA foreign_keys=ON")
    assert reopened.execute("PRAGMA user_version").fetchone() == (8,)
    assert history(reopened) == [
        (migration.version, migration.name, migration.checksum) for migration in MIGRATIONS
    ]
    assert reopened.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert reopened.execute("PRAGMA foreign_key_check").fetchall() == []
    assert reopened.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    names = {row[0] for row in reopened.execute("SELECT name FROM sqlite_master")}
    assert "image_geometry_recipes_v0008_new" not in names
    assert "audit_events_v0007" not in names
    assert not {name for name in names if "v0008" in name}

    geometry_repository, prepared_repository = _repositories(reopened)
    for expected in fixture.recipes:
        assert geometry_repository.get(expected.recipe_version_id) == expected
    assert (
        geometry_repository.list_by_region(SOURCE_A_ID, RECIPE_A_IDS[0]) == fixture.source_a_recipes
    )
    assert (
        geometry_repository.get_latest_by_region(SOURCE_A_ID, RECIPE_A_IDS[0])
        == fixture.source_a_recipes[-1]
    )
    assert (
        geometry_repository.list_by_region(SOURCE_B_ID, RECIPE_B_IDS[0]) == fixture.source_b_recipes
    )
    assert (
        geometry_repository.get_latest_by_region(SOURCE_B_ID, RECIPE_B_IDS[0])
        == fixture.source_b_recipes[-1]
    )
    assert geometry_repository.list_by_source(SOURCE_A_ID) == fixture.source_a_recipes
    assert geometry_repository.list_by_source(SOURCE_B_ID) == fixture.source_b_recipes
    for expected in fixture.prepared:
        assert prepared_repository.get(expected.id) == expected
        assert _natural_lookup(prepared_repository, expected) == expected
        assert prepared_repository.list_by_geometry_recipe(expected.geometry_recipe_version_id) == (
            expected,
        )
    assert prepared_repository.list_by_source(SOURCE_A_ID) == fixture.prepared[:2]
    assert prepared_repository.list_by_source(SOURCE_B_ID) == fixture.prepared[2:]
    reopened.close()


def _deterministic_application_data(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]:
    tables = (
        "source_files",
        "stored_artifacts",
        "image_geometry_recipes",
        "prepared_image_artifacts",
        "document_region_set_versions",
        "document_region_set_members",
    )
    return tuple(
        (
            table,
            tuple(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')),
        )
        for table in tables
    )


def test_equivalent_schema7_databases_rewrite_identically() -> None:
    first = build_populated_schema7()
    second = build_populated_schema7()
    database._apply_one_migration(first.connection, MIGRATIONS[7])
    database._apply_one_migration(second.connection, MIGRATIONS[7])

    assert _deterministic_application_data(first.connection) == _deterministic_application_data(
        second.connection
    )
    assert schema_object_names(first.connection) == schema_object_names(second.connection)
    first_payloads = tuple(row[20] for row in _geometry_rows(first.connection))
    second_payloads = tuple(row[20] for row in _geometry_rows(second.connection))
    assert first_payloads == second_payloads
    assert all(
        payload == geometry_serialization.image_geometry_recipe_to_json(expected)
        for payload, expected in zip(first_payloads, first.recipes, strict=True)
    )


def _replace_legacy_recipe(
    connection: sqlite3.Connection,
    recipe_id: EntityId,
    *,
    projected: dict[str, Any] | None = None,
    payload_change: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' "
        "AND name='image_geometry_recipes_no_update'"
    ).fetchone()[0]
    connection.execute("DROP TRIGGER image_geometry_recipes_no_update")
    try:
        if projected:
            assignments = ",".join(f"{column}=?" for column in projected)
            connection.execute(
                f"UPDATE image_geometry_recipes SET {assignments} WHERE recipe_version_id=?",
                (*projected.values(), str(recipe_id)),
            )
        if payload_change is not None:
            raw = connection.execute(
                "SELECT canonical_payload FROM image_geometry_recipes WHERE recipe_version_id=?",
                (str(recipe_id),),
            ).fetchone()[0]
            payload = json.loads(raw)
            payload_change(payload)
            connection.execute(
                "UPDATE image_geometry_recipes SET canonical_payload=? WHERE recipe_version_id=?",
                (
                    json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ),
                    str(recipe_id),
                ),
            )
    finally:
        connection.execute(trigger_sql)


def _set_raw_payload(connection: sqlite3.Connection, recipe_id: EntityId, payload: str) -> None:
    trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' "
        "AND name='image_geometry_recipes_no_update'"
    ).fetchone()[0]
    connection.execute("DROP TRIGGER image_geometry_recipes_no_update")
    try:
        connection.execute(
            "UPDATE image_geometry_recipes SET canonical_payload=? WHERE recipe_version_id=?",
            (payload, str(recipe_id)),
        )
    finally:
        connection.execute(trigger_sql)


def _inject_representable_corruption(fixture: PopulatedSchema7, case: str) -> None:
    connection = fixture.connection
    if case == "missing-revision":
        _replace_legacy_recipe(
            connection,
            RECIPE_A_IDS[2],
            projected={"revision": 4},
            payload_change=lambda payload: payload.__setitem__("revision", 4),
        )
    elif case == "revision-number-mismatch":
        _replace_legacy_recipe(
            connection,
            RECIPE_B_IDS[1],
            projected={"revision": 3},
        )
    elif case == "non-immediate-predecessor":
        _replace_legacy_recipe(
            connection,
            RECIPE_A_IDS[1],
            projected={"superseded_recipe_version_id": str(RECIPE_A_IDS[2])},
            payload_change=lambda payload: payload.__setitem__(
                "superseded_recipe_version_id", str(RECIPE_A_IDS[2])
            ),
        )
    elif case == "cross-source-predecessor":
        _replace_legacy_recipe(
            connection,
            RECIPE_B_IDS[1],
            projected={"superseded_recipe_version_id": str(RECIPE_A_IDS[2])},
            payload_change=lambda payload: payload.__setitem__(
                "superseded_recipe_version_id", str(RECIPE_A_IDS[2])
            ),
        )
    elif case == "projection-payload-mismatch":
        _replace_legacy_recipe(
            connection,
            RECIPE_A_IDS[0],
            projected={"quarter_turn_clockwise": 90},
        )
    elif case == "canonical-source-mismatch":
        _replace_legacy_recipe(
            connection,
            RECIPE_A_IDS[0],
            payload_change=lambda payload: payload.__setitem__("source_file_id", str(SOURCE_B_ID)),
        )
    elif case == "canonical-revision-mismatch":
        _replace_legacy_recipe(
            connection,
            RECIPE_A_IDS[0],
            payload_change=lambda payload: payload.__setitem__("revision", 2),
        )
    elif case == "malformed-json":
        _set_raw_payload(connection, RECIPE_A_IDS[0], "{synthetic-invalid-json")
    elif case == "missing-field":
        _replace_legacy_recipe(
            connection,
            RECIPE_A_IDS[0],
            payload_change=lambda payload: payload.pop("pipeline"),
        )
    elif case == "extra-field":
        _replace_legacy_recipe(
            connection,
            RECIPE_A_IDS[0],
            payload_change=lambda payload: payload.__setitem__("synthetic_extra", 1),
        )
    else:
        raise AssertionError(case)


def _assert_full_schema7_rollback(
    connection: sqlite3.Connection, expected: DatabaseSnapshot
) -> None:
    assert connection.execute("PRAGMA user_version").fetchone() == (7,)
    assert history(connection) == [
        (migration.version, migration.name, migration.checksum) for migration in MIGRATIONS[:7]
    ]
    actual = capture_snapshot(connection)
    assert actual.rows == expected.rows
    assert actual.geometry_table_sql == expected.geometry_table_sql
    assert actual.schema_objects == expected.schema_objects
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert "document_region_set_versions" not in names
    assert "document_region_set_members" not in names
    assert "image_geometry_recipes_v0008_new" not in names
    assert "audit_events_v0007" not in names
    assert not {name for name in names if "v0008" in name}
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert not connection.in_transaction
    assert connection.execute("SELECT 1").fetchone() == (1,)
    assert tuple(
        connection.execute(
            "SELECT prepared_artifact_id,geometry_recipe_version_id "
            "FROM prepared_image_artifacts ORDER BY prepared_artifact_id"
        )
    ) == (
        (str(PREPARED_IDS[0]), str(RECIPE_A_IDS[0])),
        (str(PREPARED_IDS[1]), str(RECIPE_A_IDS[2])),
        (str(PREPARED_IDS[2]), str(RECIPE_B_IDS[1])),
    )


@pytest.mark.parametrize(
    "case",
    (
        "missing-revision",
        "revision-number-mismatch",
        "non-immediate-predecessor",
        "cross-source-predecessor",
        "projection-payload-mismatch",
        "canonical-source-mismatch",
        "canonical-revision-mismatch",
        "malformed-json",
        "missing-field",
        "extra-field",
    ),
)
def test_representable_schema7_corruption_fails_closed_with_complete_rollback(
    case: str,
) -> None:
    fixture = build_populated_schema7()
    _inject_representable_corruption(fixture, case)
    expected = capture_snapshot(fixture.connection)

    with pytest.raises(PersistenceError) as caught:
        database._apply_one_migration(fixture.connection, MIGRATIONS[7])

    assert caught.value.code is PersistenceErrorCode.MIGRATION_FAILED
    _assert_full_schema7_rollback(fixture.connection, expected)
    fresh = build_populated_schema7()
    database._apply_one_migration(fresh.connection, MIGRATIONS[7])
    assert fresh.connection.execute("PRAGMA user_version").fetchone() == (8,)


def test_schema7_uniqueness_rejects_branch_and_duplicate_predecessor() -> None:
    fixture = build_populated_schema7()
    row = list(
        fixture.connection.execute(
            "SELECT * FROM image_geometry_recipes WHERE recipe_version_id=?",
            (str(RECIPE_A_IDS[2]),),
        ).fetchone()
    )
    row[0] = str(entity_id(304))
    row[2] = str(RECIPE_A_IDS[1])
    row[3] = 4
    with pytest.raises(sqlite3.IntegrityError) as caught:
        fixture.connection.execute(
            "INSERT INTO image_geometry_recipes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(row),
        )
    assert translate_driver_error(caught.value).code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    assert fixture.connection.execute("SELECT count(*) FROM image_geometry_recipes").fetchone() == (
        5,
    )


def _legacy_rows(fixture: PopulatedSchema7) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        fixture.connection.execute(
            "SELECT * FROM image_geometry_recipes ORDER BY source_file_id,revision"
        )
    )


@pytest.mark.parametrize(
    "case",
    (
        "branch",
        "missing-predecessor",
        "cross-source-predecessor",
        "repeated-predecessor",
        "non-contiguous-revisions",
    ),
)
def test_pure_legacy_chain_validator_rejects_schema_constrained_states(case: str) -> None:
    fixture = build_populated_schema7()
    rows = _legacy_rows(fixture)
    a1, a2, a3, b1, _b2 = rows
    if case == "branch":
        branch = list(a2)
        branch[0] = str(entity_id(399))
        chain = (a1, a2, tuple(branch))
        by_id = {row[0]: row for row in chain}
    elif case == "missing-predecessor":
        changed = list(a2)
        changed[2] = str(entity_id(999))
        chain = (a1, tuple(changed))
        by_id = {row[0]: row for row in chain}
    elif case == "cross-source-predecessor":
        changed = list(a2)
        changed[2] = b1[0]
        chain = (a1, tuple(changed))
        by_id = {row[0]: row for row in (*chain, b1)}
    elif case == "repeated-predecessor":
        changed = list(a3)
        changed[2] = a1[0]
        chain = (a1, a2, tuple(changed))
        by_id = {row[0]: row for row in chain}
    else:
        chain = (a1, a3)
        by_id = {row[0]: row for row in chain}
    with pytest.raises(PersistenceError) as caught:
        _validate_legacy_chain(chain, by_id)
    assert caught.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID


class MigrationFailureProxy:
    def __init__(self, connection: sqlite3.Connection, stage: str, marker: str) -> None:
        self.connection = connection
        self.stage = stage
        self.marker = marker
        self.completed: list[str] = []
        self.geometry_insert_attempts = 0

    @property
    def in_transaction(self) -> bool:
        return self.connection.in_transaction

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()):
        normalized = " ".join(sql.split())
        if self.stage == "audit-rebuild" and normalized.startswith(
            "CREATE TABLE image_geometry_recipes_v0008_new"
        ):
            raise sqlite3.OperationalError(self.marker)
        if normalized.startswith("INSERT INTO image_geometry_recipes_v0008_new"):
            self.geometry_insert_attempts += 1
            if self.stage == "second-geometry-insert" and self.geometry_insert_attempts == 2:
                raise sqlite3.OperationalError(self.marker)
        if self.stage == "region-schema" and normalized.startswith(
            "CREATE TABLE document_region_set_members"
        ):
            raise sqlite3.OperationalError(self.marker)
        result = self.connection.execute(sql, parameters)
        self.completed.append(normalized)
        return result

    def close(self) -> None:
        self.connection.close()

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.connection, name)


@pytest.mark.parametrize(
    ("stage", "expected_insert_attempts", "expected_staged_rows"),
    (
        ("audit-rebuild", 0, 0),
        ("second-geometry-insert", 2, 1),
        ("region-schema", 5, 5),
    ),
)
def test_injected_mid_migration_failure_restores_complete_schema7_state(
    stage: str, expected_insert_attempts: int, expected_staged_rows: int
) -> None:
    fixture = build_populated_schema7()
    expected = fixture.before
    private_marker = f"synthetic-private-{stage}-driver-detail"
    proxy = MigrationFailureProxy(fixture.connection, stage, private_marker)

    with pytest.raises(PersistenceError) as caught:
        database._apply_one_migration(proxy, MIGRATIONS[7])  # type: ignore[arg-type]

    assert caught.value.code is PersistenceErrorCode.MIGRATION_FAILED
    assert private_marker not in str(caught.value)
    assert private_marker not in repr(caught.value)
    assert proxy.geometry_insert_attempts == expected_insert_attempts
    completed_inserts = tuple(
        sql
        for sql in proxy.completed
        if sql.startswith("INSERT INTO image_geometry_recipes_v0008_new")
    )
    assert len(completed_inserts) == expected_staged_rows
    if stage == "audit-rebuild":
        assert any(sql.startswith("ALTER TABLE audit_events RENAME") for sql in proxy.completed)
    elif stage == "second-geometry-insert":
        assert any(
            sql.startswith("CREATE TABLE image_geometry_recipes_v0008_new")
            for sql in proxy.completed
        )
    else:
        assert any(sql.startswith("DROP TABLE image_geometry_recipes") for sql in proxy.completed)
        assert any(
            sql.startswith("CREATE TABLE document_region_set_versions") for sql in proxy.completed
        )
    _assert_full_schema7_rollback(fixture.connection, expected)

    fresh = build_populated_schema7()
    database._apply_one_migration(fresh.connection, MIGRATIONS[7])
    assert fresh.connection.execute("PRAGMA user_version").fetchone() == (8,)
