from __future__ import annotations

from uuid import UUID

import pytest

from document_intake.domain import (
    Document,
    DocumentType,
    EntityId,
    InvalidTransitionError,
    can_transition_document,
    transition_document,
)
from document_intake.domain import (
    DocumentWorkflowStatus as S,
)


def eid(i: int) -> EntityId:
    return EntityId(UUID(int=i))


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.NEW, S.NEEDS_SEGMENTATION),
        (S.NEW, S.NEEDS_CLASSIFICATION),
        (S.NEEDS_SEGMENTATION, S.NEEDS_CLASSIFICATION),
        (S.NEEDS_CLASSIFICATION, S.OCR_READY),
        (S.OCR_READY, S.NEEDS_REVIEW),
        (S.NEEDS_REVIEW, S.VERIFIED),
        (S.NEEDS_REVIEW, S.INCOMPLETE),
        (S.INCOMPLETE, S.NEEDS_REVIEW),
        (S.VERIFIED, S.READY_FOR_EXPORT),
        (S.READY_FOR_EXPORT, S.EXPORTED),
    ],
)
def test_allowed_transitions(current: S, target: S) -> None:
    document = Document(eid(1), DocumentType.PASSPORT, current)
    assert can_transition_document(current, target)
    transition_document(document, target)
    assert document.workflow_status == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.NEW, S.VERIFIED),
        (S.NEEDS_CLASSIFICATION, S.EXPORTED),
        (S.VERIFIED, S.NEEDS_REVIEW),
        (S.EXPORTED, S.NEW),
    ],
)
def test_invalid_transitions_do_not_mutate(current: S, target: S) -> None:
    document = Document(eid(1), DocumentType.PASSPORT, current)
    with pytest.raises(InvalidTransitionError):
        transition_document(document, target)
    assert document.workflow_status == current


def test_document_workflow_status_is_read_only() -> None:
    document = Document(eid(1), DocumentType.PASSPORT, S.NEW)
    with pytest.raises(AttributeError):
        document.workflow_status = S.VERIFIED  # type: ignore[misc]
    assert document.workflow_status == S.NEW
