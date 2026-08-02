import sqlite3
from dataclasses import replace

import pytest

from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import entity_id
from tests.support.pr013_persistence import natural_kwargs, records, schema9_uow


def persist(uow, values):
    composition, version, artifact, stored = values
    uow.stored_artifacts.add(stored)
    uow.document_side_compositions.add_composition(composition)
    uow.document_side_compositions.add_version(version)
    uow.document_side_compositions.add_artifact(artifact)
    return composition, version, artifact


def test_create_load_exact_natural_key_and_one_to_one() -> None:
    connection, uow = schema9_uow()
    composition, version, artifact = persist(uow, records())
    connection.commit()
    assert uow.document_side_compositions.get_composition(composition.id) == composition
    assert uow.document_side_compositions.get_version(version.id) == version
    assert uow.document_side_compositions.get_artifact(artifact.id) == artifact
    assert (
        uow.document_side_compositions.get_artifact_by_composition_version(version.id) == artifact
    )
    assert uow.document_side_compositions.get_by_natural_key(**natural_kwargs(version)) == version
    assert not any(
        hasattr(uow.document_side_compositions, name)
        for name in ("update", "replace", "delete", "supersede", "get_latest", "set_latest")
    )


def test_side_order_is_part_of_natural_key() -> None:
    connection, uow = schema9_uow()
    _, version, _ = persist(uow, records())
    connection.commit()
    _, swapped, _, _ = records(swapped=True)
    assert uow.document_side_compositions.get_by_natural_key(**natural_kwargs(swapped)) is None
    assert uow.document_side_compositions.get_by_natural_key(**natural_kwargs(version)) == version


def test_immutable_triggers_and_cardinality_constraints() -> None:
    connection, uow = schema9_uow()
    _, version, _ = persist(uow, records())
    connection.commit()
    for sql in (
        "UPDATE document_side_compositions SET id=id",
        "DELETE FROM document_side_composition_versions",
        "UPDATE prepared_composition_artifacts SET width=width",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql)
    with pytest.raises(PersistenceError) as captured:
        uow.document_side_compositions.add_version(version)
    assert captured.value.code in {
        PersistenceErrorCode.ENTITY_ALREADY_EXISTS,
        PersistenceErrorCode.PERSISTENCE_CONSTRAINT,
    }


def test_corrupt_payload_and_projection_fail_closed() -> None:
    connection, uow = schema9_uow()
    _, version, _ = persist(uow, records())
    connection.commit()
    connection.execute("DROP TRIGGER document_side_composition_versions_no_update")
    connection.execute(
        "UPDATE document_side_composition_versions SET canonical_payload='{}' WHERE id=?",
        (str(version.id),),
    )
    with pytest.raises(PersistenceError) as captured:
        uow.document_side_compositions.get_version(version.id)
    assert captured.value.code is PersistenceErrorCode.PERSISTED_DATA_INVALID
    connection.rollback()


def _composite_foreign_keys(connection: sqlite3.Connection) -> set[tuple[object, ...]]:
    grouped: dict[int, list[tuple[object, ...]]] = {}
    for row in connection.execute("PRAGMA foreign_key_list(document_side_composition_versions)"):
        grouped.setdefault(row[0], []).append(row)
    return {
        (
            rows[0][2],
            tuple(row[3] for row in sorted(rows, key=lambda item: item[1])),
            tuple(row[4] for row in sorted(rows, key=lambda item: item[1])),
        )
        for rows in grouped.values()
        if len(rows) == 2
    }


def test_schema_has_four_composite_member_foreign_keys_and_both_lineage_guards() -> None:
    connection, _ = schema9_uow()
    assert _composite_foreign_keys(connection) == {
        (
            "document_region_set_members",
            ("side_1_region_set_version_id", "side_1_region_id"),
            ("region_set_version_id", "region_id"),
        ),
        (
            "document_region_set_members",
            ("side_1_region_set_version_id", "side_1_geometry_recipe_version_id"),
            ("region_set_version_id", "geometry_recipe_version_id"),
        ),
        (
            "document_region_set_members",
            ("side_2_region_set_version_id", "side_2_region_id"),
            ("region_set_version_id", "region_id"),
        ),
        (
            "document_region_set_members",
            ("side_2_region_set_version_id", "side_2_geometry_recipe_version_id"),
            ("region_set_version_id", "geometry_recipe_version_id"),
        ),
    }
    triggers = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
            ("document_side_composition_versions",),
        )
    }
    assert {
        "document_side_composition_versions_side_1_lineage_guard",
        "document_side_composition_versions_side_2_lineage_guard",
    } <= triggers


@pytest.mark.parametrize("side", (1, 2))
@pytest.mark.parametrize(
    ("case", "lineage"),
    (
        ("region_from_another_set", (60, 20, 31, 30)),
        ("recipe_from_another_set", (60, 20, 30, 31)),
        ("source_differs_from_set", (60, 21, 30, 30)),
        ("recipe_source_differs", (62, 20, 31, 31)),
        ("recipe_region_differs", (63, 20, 32, 30)),
        ("independently_valid_member_pairs", (64, 20, 30, 32)),
    ),
)
def test_each_side_rejects_every_malformed_confirmed_lineage(
    side: int, case: str, lineage: tuple[int, int, int, int]
) -> None:
    del case
    connection, uow = schema9_uow(lineage_matrix=True)
    composition, version, _, _ = records(swapped=side == 2)
    fields = {
        f"side_{side}_region_set_version_id": entity_id(lineage[0]),
        f"side_{side}_source_file_id": entity_id(lineage[1]),
        f"side_{side}_region_id": entity_id(lineage[2]),
        f"side_{side}_geometry_recipe_version_id": entity_id(lineage[3]),
    }
    malformed = replace(version, **fields)
    uow.document_side_compositions.add_composition(composition)
    with pytest.raises(PersistenceError) as captured:
        uow.document_side_compositions.add_version(malformed)
    assert captured.value.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    ("variant", "swapped"),
    (
        ("different_sources", False),
        ("same_source", False),
        ("same_region_set", False),
        ("different_sources", True),
        ("same_source", True),
        ("same_region_set", True),
    ),
)
def test_valid_lineage_variants_and_explicit_order_still_persist(
    variant: str, swapped: bool
) -> None:
    connection, uow = schema9_uow(variant=variant)
    _, version, _ = persist(uow, records(variant=variant, swapped=swapped))
    connection.commit()
    assert uow.document_side_compositions.get_version(version.id) == version
    assert uow.document_side_compositions.get_by_natural_key(**natural_kwargs(version)) == version
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
