# ruff: noqa: E501
"""PR-012 deterministic document-region lineages and immutable sets."""

from typing import Any

from document_intake.domain.value_objects import EntityId
from document_intake.persistence import geometry_serialization as geometry_ser
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations.model import Migration, migration_checksum
from document_intake.persistence.migrations.v0007_prepared_jpeg import (
    _AUDIT_CREATE as V7_AUDIT_CREATE,
)

_AUDIT_CREATE = V7_AUDIT_CREATE.replace(
    "'PREPARED_JPEG_CREATED'", "'PREPARED_JPEG_CREATED','DOCUMENT_REGION_SET_CONFIRMED'"
).replace("'PREPARED_IMAGE_ARTIFACT'", "'PREPARED_IMAGE_ARTIFACT','DOCUMENT_REGION_SET'")
_GEOMETRY_CREATE = """CREATE TABLE image_geometry_recipes_v0008_new(recipe_version_id TEXT PRIMARY KEY NOT NULL CHECK(length(recipe_version_id)=36), source_file_id TEXT NOT NULL REFERENCES source_files(id), region_id TEXT NOT NULL CHECK(length(region_id)=36), superseded_recipe_version_id TEXT NULL REFERENCES image_geometry_recipes_v0008_new(recipe_version_id), revision INTEGER NOT NULL CHECK(revision>=1), coordinate_space TEXT NOT NULL CHECK(coordinate_space='SOURCE_EFFECTIVE_PIXELS_V1'), source_effective_width INTEGER NOT NULL CHECK(source_effective_width>=1), source_effective_height INTEGER NOT NULL CHECK(source_effective_height>=1), quarter_turn_clockwise INTEGER NOT NULL CHECK(quarter_turn_clockwise IN (0,90,180,270)), top_left_x INTEGER NOT NULL, top_left_y INTEGER NOT NULL, top_right_x INTEGER NOT NULL, top_right_y INTEGER NOT NULL, bottom_right_x INTEGER NOT NULL, bottom_right_y INTEGER NOT NULL, bottom_left_x INTEGER NOT NULL, bottom_left_y INTEGER NOT NULL, geometry_pipeline_id TEXT NOT NULL CHECK(geometry_pipeline_id='PILLOW_QUAD_BICUBIC'), geometry_pipeline_version INTEGER NOT NULL CHECK(geometry_pipeline_version=1), created_at_utc TEXT NOT NULL, canonical_payload TEXT NOT NULL CHECK(length(canonical_payload)>=1), UNIQUE(source_file_id,region_id,revision), UNIQUE(superseded_recipe_version_id), CHECK((revision=1 AND superseded_recipe_version_id IS NULL AND region_id=recipe_version_id) OR (revision>1 AND superseded_recipe_version_id IS NOT NULL AND region_id<>recipe_version_id)))"""
TRANSFORM_ID = "PR012_GEOMETRY_PAYLOAD_V7_TO_V8_V1"


def _legacy_projection(row: tuple[Any, ...]) -> tuple[Any, ...]:
    return tuple(row[:19])


def _recipe_projection(recipe: Any) -> tuple[Any, ...]:
    columns = geometry_ser.image_geometry_recipe_columns(recipe)
    return (columns[0], columns[1], *columns[3:])


def _validated_legacy_rows(connection: Any) -> tuple[tuple[Any, ...], ...]:
    rows = tuple(
        connection.execute(
            "SELECT recipe_version_id,source_file_id,superseded_recipe_version_id,revision,coordinate_space,source_effective_width,source_effective_height,quarter_turn_clockwise,top_left_x,top_left_y,top_right_x,top_right_y,bottom_right_x,bottom_right_y,bottom_left_x,bottom_left_y,geometry_pipeline_id,geometry_pipeline_version,created_at_utc,canonical_payload FROM image_geometry_recipes ORDER BY source_file_id,revision,recipe_version_id"
        ).fetchall()
    )
    by_id = {row[0]: row for row in rows}
    if len(by_id) != len(rows):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    for source_id in sorted({row[1] for row in rows}):
        chain = tuple(row for row in rows if row[1] == source_id)
        _validate_legacy_chain(chain, by_id)
    return rows


def _validate_legacy_chain(
    chain: tuple[tuple[Any, ...], ...], by_id: dict[Any, tuple[Any, ...]]
) -> None:
    seen: set[Any] = set()
    for revision, row in enumerate(chain, 1):
        predecessor = row[2]
        if row[3] != revision or (revision == 1) != (predecessor is None):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        if revision > 1 and (predecessor != chain[revision - 2][0] or predecessor in seen):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        if predecessor is not None and (
            predecessor not in by_id or by_id[predecessor][1] != row[1]
        ):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        seen.add(predecessor)


def _transform_geometry_payloads(connection: Any) -> None:
    rows = _validated_legacy_rows(connection)
    roots = {row[1]: EntityId.parse(row[0]) for row in rows if row[3] == 1}
    inserted = 0
    for row in rows:
        root = roots.get(row[1])
        if root is None:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        recipe = geometry_ser.image_geometry_recipe_from_json_v7(row[19], root)
        if _recipe_projection(recipe) != _legacy_projection(row):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        columns = geometry_ser.image_geometry_recipe_columns(recipe)
        connection.execute(
            "INSERT INTO image_geometry_recipes_v0008_new(recipe_version_id,source_file_id,region_id,superseded_recipe_version_id,revision,coordinate_space,source_effective_width,source_effective_height,quarter_turn_clockwise,top_left_x,top_left_y,top_right_x,top_right_y,bottom_right_x,bottom_right_y,bottom_left_x,bottom_left_y,geometry_pipeline_id,geometry_pipeline_version,created_at_utc,canonical_payload) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*columns, geometry_ser.image_geometry_recipe_to_json(recipe)),
        )
        inserted += 1
    count = connection.execute("SELECT count(*) FROM image_geometry_recipes_v0008_new").fetchone()[
        0
    ]
    if count != inserted:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)


STATEMENTS = (
    "ALTER TABLE audit_events RENAME TO audit_events_v0007",
    _AUDIT_CREATE,
    "INSERT INTO audit_events SELECT * FROM audit_events_v0007",
    "DROP TABLE audit_events_v0007",
    "CREATE INDEX audit_events_subject_order_idx ON audit_events(subject_type,subject_id,occurred_at_utc,event_id)",
    "CREATE INDEX audit_events_correlation_order_idx ON audit_events(correlation_id,occurred_at_utc,event_id) WHERE correlation_id IS NOT NULL",
    "CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_events immutable'); END",
    "CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_events immutable'); END",
    "CREATE TRIGGER audit_events_no_replace BEFORE INSERT ON audit_events WHEN EXISTS(SELECT 1 FROM audit_events WHERE event_id=NEW.event_id) BEGIN SELECT RAISE(ABORT,'audit_events duplicate'); END",
    _GEOMETRY_CREATE,
    "DROP TABLE image_geometry_recipes",
    "ALTER TABLE image_geometry_recipes_v0008_new RENAME TO image_geometry_recipes",
    "CREATE INDEX image_geometry_recipes_source_region_order_idx ON image_geometry_recipes(source_file_id,region_id,revision,created_at_utc,recipe_version_id)",
    "CREATE TRIGGER image_geometry_recipes_no_update BEFORE UPDATE ON image_geometry_recipes BEGIN SELECT RAISE(ABORT,'image_geometry_recipes_append_only'); END",
    "CREATE TRIGGER image_geometry_recipes_no_delete BEFORE DELETE ON image_geometry_recipes BEGIN SELECT RAISE(ABORT,'image_geometry_recipes_append_only'); END",
    "CREATE TRIGGER image_geometry_recipes_no_replace BEFORE INSERT ON image_geometry_recipes WHEN EXISTS(SELECT 1 FROM image_geometry_recipes WHERE recipe_version_id=NEW.recipe_version_id) BEGIN SELECT RAISE(ABORT,'image_geometry_recipes_duplicate'); END",
    "CREATE TABLE document_region_set_versions(region_set_version_id TEXT PRIMARY KEY NOT NULL CHECK(length(region_set_version_id)=36),source_file_id TEXT NOT NULL REFERENCES source_files(id),superseded_region_set_version_id TEXT NULL REFERENCES document_region_set_versions(region_set_version_id),revision INTEGER NOT NULL CHECK(revision>=1),confirmed_at_utc TEXT NOT NULL,confirmed_by_actor_id TEXT NOT NULL CHECK(length(confirmed_by_actor_id)=36),confirmed_by_actor_kind TEXT NOT NULL CHECK(confirmed_by_actor_kind IN ('OPERATOR','ADMIN','SYSTEM')),canonical_payload TEXT NOT NULL,UNIQUE(source_file_id,revision),UNIQUE(superseded_region_set_version_id))",
    "CREATE TABLE document_region_set_members(region_set_version_id TEXT NOT NULL REFERENCES document_region_set_versions(region_set_version_id),order_index INTEGER NOT NULL CHECK(order_index IN (1,2)),region_id TEXT NOT NULL CHECK(length(region_id)=36),geometry_recipe_version_id TEXT NOT NULL REFERENCES image_geometry_recipes(recipe_version_id),PRIMARY KEY(region_set_version_id,order_index),UNIQUE(region_set_version_id,region_id),UNIQUE(region_set_version_id,geometry_recipe_version_id))",
    "CREATE INDEX document_region_sets_source_order_idx ON document_region_set_versions(source_file_id,revision)",
    "CREATE TRIGGER document_region_set_versions_no_update BEFORE UPDATE ON document_region_set_versions BEGIN SELECT RAISE(ABORT,'document_region_set_versions immutable'); END",
    "CREATE TRIGGER document_region_set_versions_no_delete BEFORE DELETE ON document_region_set_versions BEGIN SELECT RAISE(ABORT,'document_region_set_versions immutable'); END",
    "CREATE TRIGGER document_region_set_versions_no_replace BEFORE INSERT ON document_region_set_versions WHEN EXISTS(SELECT 1 FROM document_region_set_versions WHERE region_set_version_id=NEW.region_set_version_id) BEGIN SELECT RAISE(ABORT,'document_region_set_versions duplicate'); END",
    "CREATE TRIGGER document_region_set_members_no_update BEFORE UPDATE ON document_region_set_members BEGIN SELECT RAISE(ABORT,'document_region_set_members immutable'); END",
    "CREATE TRIGGER document_region_set_members_no_delete BEFORE DELETE ON document_region_set_members BEGIN SELECT RAISE(ABORT,'document_region_set_members immutable'); END",
    "CREATE TRIGGER document_region_set_members_no_replace BEFORE INSERT ON document_region_set_members WHEN EXISTS(SELECT 1 FROM document_region_set_members WHERE region_set_version_id=NEW.region_set_version_id AND order_index=NEW.order_index) BEGIN SELECT RAISE(ABORT,'document_region_set_members duplicate'); END",
)
MIGRATION = Migration(
    8,
    "document_regions_pr012",
    STATEMENTS,
    migration_checksum(
        STATEMENTS,
        foreign_key_mode="DISABLED_DURING_TABLE_REBUILD",
        transform_id=TRANSFORM_ID,
        transform_after_statement=9,
    ),
    foreign_key_mode="DISABLED_DURING_TABLE_REBUILD",
    transform_id=TRANSFORM_ID,
    transform_after_statement=9,
    transform=_transform_geometry_payloads,
)
