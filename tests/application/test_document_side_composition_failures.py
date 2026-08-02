from __future__ import annotations

import pytest

from document_intake.domain.document_side_composition import (
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
)
from document_intake.persistence.errors import PersistenceErrorCode
from tests.support.pr013_application import Factory, Storage, command, invoke


def _assert_error(
    factory: Factory,
    storage: Storage,
    expected: DocumentSideCompositionErrorCode,
) -> None:
    with pytest.raises(DocumentSideCompositionError) as captured:
        invoke(factory, storage)
    assert captured.value.code is expected
    assert str(captured.value) == expected.value


def _assert_unreferenced_publication(factory: Factory, storage: Storage) -> None:
    write = factory.units[1]
    assert storage.publish_calls == 1
    assert len(storage.published_objects) == 1
    assert write.committed_row_count == 0
    assert storage.delete_calls == storage.adopt_calls == 0


@pytest.mark.parametrize(
    "identity",
    (
        "composition_id",
        "composition_version_id",
        "prepared_artifact_id",
        "stored_artifact_id",
        "audit_event_id",
    ),
)
def test_every_supplied_identity_conflict_prevents_publication(identity: str) -> None:
    calls: list[str] = []
    factory = Factory(calls)
    selected = command()
    write = factory.units[1]
    if identity == "composition_id":
        write.document_side_compositions.compositions[selected.composition_id] = object()
    elif identity == "composition_version_id":
        write.document_side_compositions.versions[selected.composition_version_id] = object()
    elif identity == "prepared_artifact_id":
        write.document_side_compositions.artifacts[selected.prepared_artifact_id] = object()
    elif identity == "stored_artifact_id":
        write.stored_artifacts.values[selected.stored_artifact_id] = object()
    else:
        write.audit_events.values[selected.audit_event_id] = object()
    storage = Storage(calls)
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.IDENTITY_CONFLICT)
    assert storage.publish_attempts == storage.publish_calls == 0
    assert write.commit_attempts == write.commits == write.committed_row_count == 0


def test_natural_key_preflight_prevents_publication_and_committed_rows() -> None:
    calls: list[str] = []
    factory = Factory(calls)
    write = factory.units[1]
    write.document_side_compositions.natural = object()
    storage = Storage(calls)
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.COMPOSITION_ALREADY_EXISTS)
    assert storage.publish_attempts == storage.publish_calls == 0
    assert write.commit_attempts == write.commits == write.committed_row_count == 0


def test_stale_write_snapshot_fails_before_publication() -> None:
    calls: list[str] = []
    factory = Factory(calls)
    storage = Storage(calls)
    factory.units[1].source_files.values.pop(command().side_1.source_file_id)
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID)
    assert storage.publish_attempts == 0


def test_storage_publication_exception_is_sanitized_and_rolls_back() -> None:
    calls: list[str] = []
    factory = Factory(calls)
    storage = Storage(calls)
    storage.publish_error = RuntimeError("private storage detail")
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.STORAGE_PUBLICATION_FAILED)
    write = factory.units[1]
    assert storage.publish_attempts == 1
    assert storage.publish_calls == 0
    assert write.commit_attempts == write.commits == write.committed_row_count == 0


@pytest.mark.parametrize(
    "mismatch",
    (
        "artifact_id",
        "artifact_kind",
        "object_generation",
        "plaintext_length",
        "plaintext_sha256",
        "created_at",
    ),
)
def test_every_returned_storage_record_mismatch_leaves_only_orphan_candidate(
    mismatch: str,
) -> None:
    calls: list[str] = []
    factory = Factory(calls)
    storage = Storage(calls, mismatch=mismatch)
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.STORAGE_PUBLICATION_FAILED)
    _assert_unreferenced_publication(factory, storage)
    assert factory.units[1].commit_attempts == 0


@pytest.mark.parametrize(
    "stage",
    (
        "stored_artifacts.add",
        "document_side_compositions.add_composition",
        "document_side_compositions.add_version",
        "document_side_compositions.add_artifact",
        "audit_events.add",
    ),
)
def test_every_ordered_insert_constraint_failure_rolls_back_after_publication(
    stage: str,
) -> None:
    calls: list[str] = []
    factory = Factory(calls)
    write = factory.units[1]
    write.fail_stage = stage
    storage = Storage(calls)
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.PERSISTENCE_CONFLICT)
    _assert_unreferenced_publication(factory, storage)
    assert write.commit_attempts == write.commits == 0
    assert write.rollbacks == 1


@pytest.mark.parametrize(
    ("code", "expected"),
    (
        (
            PersistenceErrorCode.ENTITY_ALREADY_EXISTS,
            DocumentSideCompositionErrorCode.PERSISTENCE_CONFLICT,
        ),
        (
            PersistenceErrorCode.PERSISTENCE_CONSTRAINT,
            DocumentSideCompositionErrorCode.PERSISTENCE_CONFLICT,
        ),
        (
            PersistenceErrorCode.PERSISTED_DATA_INVALID,
            DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID,
        ),
        (
            PersistenceErrorCode.PERSISTENCE_UNEXPECTED,
            DocumentSideCompositionErrorCode.PERSISTENCE_FAILED,
        ),
    ),
)
def test_ordered_insert_persistence_error_mapping(
    code: PersistenceErrorCode, expected: DocumentSideCompositionErrorCode
) -> None:
    calls: list[str] = []
    factory = Factory(calls)
    factory.units[1].fail_stage = "audit_events.add"
    factory.units[1].fail_code = code
    storage = Storage(calls)
    _assert_error(factory, storage, expected)
    _assert_unreferenced_publication(factory, storage)


def test_late_natural_key_race_leaves_orphan_and_no_rows() -> None:
    calls: list[str] = []
    factory = Factory(calls)
    write = factory.units[1]
    assert write.document_side_compositions.natural is None
    write.fail_stage = "document_side_compositions.add_version"
    write.fail_code = PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    storage = Storage(calls)
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.PERSISTENCE_CONFLICT)
    _assert_unreferenced_publication(factory, storage)
    assert write.rollbacks == 1


def test_commit_failure_rolls_back_rows_but_retains_orphan_candidate() -> None:
    calls: list[str] = []
    factory = Factory(calls)
    write = factory.units[1]
    write.commit_error = RuntimeError("private commit detail")
    storage = Storage(calls)
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.COMMIT_FAILED)
    _assert_unreferenced_publication(factory, storage)
    assert write.commit_attempts == 1
    assert write.commits == 0
    assert write.rollbacks == 1


def test_failed_write_uow_exit_after_commit_returns_no_result_but_rows_are_committed() -> None:
    calls: list[str] = []
    factory = Factory(calls)
    write = factory.units[1]
    write.exit_error = RuntimeError("private exit detail")
    storage = Storage(calls)
    _assert_error(factory, storage, DocumentSideCompositionErrorCode.COMMIT_FAILED)
    assert write.commit_attempts == write.commits == 1
    assert write.committed_row_count == 5
    assert write.rollbacks == 0
    assert storage.publish_calls == 1
    assert storage.delete_calls == storage.adopt_calls == 0
