from __future__ import annotations

import json

import pytest

from document_intake.persistence import serialization as ser
from document_intake.persistence.database import IdentityRepo, PersonRepo
from document_intake.persistence.errors import (
    PersistenceError,
    PersistenceErrorCode,
    translate_driver_error,
)
from tests.persistence.test_repositories import (
    FakeUow,
    application,
    candidate,
    document,
    eid,
    identity_document,
    migrated_connection,
    person,
    snapshot,
    terminal,
)


class IntegrityError(Exception):
    def __init__(self, message: str, sqlite_errorcode: int = 1811) -> None:
        self.sqlite_errorcode = sqlite_errorcode
        super().__init__(message)


CONTROLLED_DUPLICATE_MESSAGES = (
    "audit_events duplicate",
    "image_geometry_recipes_duplicate",
    "prepared_image_artifacts duplicate",
    "document_region_set_versions duplicate",
    "document_region_set_members duplicate",
)


@pytest.mark.parametrize("message", CONTROLLED_DUPLICATE_MESSAGES)
def test_controlled_duplicate_trigger_requires_explicit_duplicate_context(message: str) -> None:
    duplicate = translate_driver_error(IntegrityError(message), duplicate_is_already_exists=True)
    constraint = translate_driver_error(IntegrityError(message))

    assert duplicate.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    assert message not in str(duplicate)
    assert message not in repr(duplicate)
    assert constraint.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT


def test_controlled_duplicate_trigger_matching_allows_only_case_and_outer_space() -> None:
    translated = translate_driver_error(
        IntegrityError("  DOCUMENT_REGION_SET_VERSIONS DUPLICATE  "),
        duplicate_is_already_exists=True,
    )
    assert translated.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS


@pytest.mark.parametrize(
    "message",
    [
        "document_region_set_versions duplicate extra",
        "prefix document_region_set_versions duplicate",
        "document_region_set_versions  duplicate",
        "document_region_set_versions_duplicate",
        "arbitrary duplicate",
        "duplicate",
    ],
)
def test_controlled_duplicate_trigger_near_matches_remain_constraints(message: str) -> None:
    translated = translate_driver_error(IntegrityError(message), duplicate_is_already_exists=True)
    assert translated.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT


@pytest.mark.parametrize(
    "message",
    [
        "audit_events immutable",
        "image_geometry_recipes_append_only",
        "prepared_image_artifacts immutable",
        "document_region_set_versions immutable",
        "document_region_set_members immutable",
        "ERR_STORED_ARTIFACT_IMMUTABLE",
        "ERR_SNAPSHOT_IMMUTABLE",
        "ERR_SNAPSHOT_ARTIFACT_IMMUTABLE",
        "ERR_SNAPSHOT_ARTIFACT_ORDINAL",
    ],
)
def test_non_duplicate_trigger_failures_remain_constraints(message: str) -> None:
    translated = translate_driver_error(IntegrityError(message), duplicate_is_already_exists=True)
    assert translated.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT


@pytest.mark.parametrize("sqlite_errorcode", [1555, 2067])
def test_native_duplicate_codes_remain_already_exists(sqlite_errorcode: int) -> None:
    translated = translate_driver_error(
        IntegrityError("synthetic constraint", sqlite_errorcode),
        duplicate_is_already_exists=True,
    )
    assert translated.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS


@pytest.mark.parametrize("sqlite_errorcode", [787, 1299, 275])
def test_native_non_duplicate_constraint_codes_remain_constraints(
    sqlite_errorcode: int,
) -> None:
    translated = translate_driver_error(
        IntegrityError("synthetic constraint", sqlite_errorcode),
        duplicate_is_already_exists=True,
    )
    assert translated.code is PersistenceErrorCode.PERSISTENCE_CONSTRAINT


def test_unknown_driver_error_remains_unexpected_and_private() -> None:
    raw_message = "synthetic raw driver detail"
    translated = translate_driver_error(RuntimeError(raw_message))
    assert translated.code is PersistenceErrorCode.PERSISTENCE_UNEXPECTED
    assert raw_message not in str(translated)
    assert raw_message not in repr(translated)


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


@pytest.mark.parametrize("invalid", ["true", 1, 0, [], {}, None])
def test_terminal_is_active_requires_exact_boolean(invalid: object) -> None:
    payload = json.loads(ser.terminal_to_json(terminal()))
    payload["is_active"] = invalid
    with pytest.raises(PersistenceError) as excinfo:
        ser.terminal_from_json(json.dumps(payload))
    assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_canonical_collection_keys_are_required() -> None:
    app = application()
    snap = snapshot(application())
    cases = (
        (ser.document_to_json(document()), ser.document_from_json, "side_ids"),
        (
            ser.candidate_to_json(candidate()),
            ser.candidate_from_json,
            "validation_results",
        ),
        (ser.application_to_json(app), ser.application_from_json, "assignments"),
        (ser.application_to_json(app), ser.application_from_json, "verified_fields"),
        (ser.application_to_json(app), ser.application_from_json, "validation_issues"),
        (
            ser.snapshot_to_json(snap),
            ser.snapshot_from_json,
            "document_artifact_refs",
        ),
    )
    for encoded, deserializer, missing_key in cases:
        payload = json.loads(encoded)
        del payload[missing_key]
        with pytest.raises(PersistenceError) as excinfo:
            deserializer(json.dumps(payload))
        assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_assignment_projection_serializes_person_id_once() -> None:
    encoded = ser.dumps(ser._assignment_to_dict(application().assignments[0]))
    assert encoded.count('"person_id"') == 1
