from __future__ import annotations

import json

import pytest

from document_intake.persistence import serialization as ser
from document_intake.persistence.database import IdentityRepo, PersonRepo
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.persistence.test_repositories import (
    FakeUow,
    eid,
    identity_document,
    migrated_connection,
    person,
)


def test_duplicate_and_constraint_failures_have_distinct_stable_codes() -> None:
    connection = migrated_connection()
    uow = FakeUow(connection)
    persons = PersonRepo(uow)
    persons.add(person())

    with pytest.raises(PersistenceError) as duplicate:
        persons.add(person())
    assert duplicate.value.code == PersistenceErrorCode.ENTITY_ALREADY_EXISTS

    connection.execute("DELETE FROM persons")
    with pytest.raises(PersistenceError) as foreign_key:
        IdentityRepo(uow).add(identity_document())
    assert foreign_key.value.code == PersistenceErrorCode.PERSISTENCE_CONSTRAINT

    with pytest.raises(PersistenceError) as not_null:
        persons._execute(
            "INSERT INTO persons(id, payload) VALUES (?, ?)",
            (str(eid(2)), None),
        )
    assert not_null.value.code == PersistenceErrorCode.PERSISTENCE_CONSTRAINT


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "{}",
        json.dumps({"id": str(eid(1)), "birth_date": "not-a-date"}),
        json.dumps(
            {
                "id": str(eid(10)),
                "person_id": str(eid(1)),
                "document_type": "UNKNOWN_ENUM",
            }
        ),
        json.dumps({"id": str(eid(1)), "full_name_latin": " padded "}),
    ],
)
def test_malformed_and_invalid_domain_payloads_are_normalized(payload: str) -> None:
    deserializer = ser.identity_from_json if "document_type" in payload else ser.person_from_json
    with pytest.raises(PersistenceError) as excinfo:
        deserializer(payload)
    assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID
    assert payload not in str(excinfo.value)


class UnexpectedConnection:
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> object:
        _ = (sql, parameters)
        raise RuntimeError("synthetic raw driver detail")


class UnexpectedUow:
    def _connection(self) -> UnexpectedConnection:
        return UnexpectedConnection()


def test_unexpected_driver_failure_is_normalized_without_raw_detail() -> None:
    repo = PersonRepo(UnexpectedUow())  # type: ignore[arg-type]
    with pytest.raises(PersistenceError) as excinfo:
        repo.get(eid(1))
    assert excinfo.value.code == PersistenceErrorCode.PERSISTENCE_UNEXPECTED
    assert "synthetic raw driver detail" not in str(excinfo.value)


def test_missing_entity_update_remains_distinct() -> None:
    repo = PersonRepo(FakeUow(migrated_connection()))
    with pytest.raises(PersistenceError) as excinfo:
        repo.update(person())
    assert excinfo.value.code == PersistenceErrorCode.ENTITY_NOT_FOUND
