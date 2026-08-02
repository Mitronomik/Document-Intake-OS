import sqlite3

import pytest

from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
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
