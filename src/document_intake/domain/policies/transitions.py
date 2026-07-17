"""Document workflow transition policy."""

from __future__ import annotations

from document_intake.domain.entities import Document
from document_intake.domain.enums import DocumentWorkflowStatus
from document_intake.domain.errors import InvalidTransitionError

_ALLOWED = frozenset(
    {
        (DocumentWorkflowStatus.NEW, DocumentWorkflowStatus.NEEDS_SEGMENTATION),
        (DocumentWorkflowStatus.NEW, DocumentWorkflowStatus.NEEDS_CLASSIFICATION),
        (DocumentWorkflowStatus.NEEDS_SEGMENTATION, DocumentWorkflowStatus.NEEDS_CLASSIFICATION),
        (DocumentWorkflowStatus.NEEDS_CLASSIFICATION, DocumentWorkflowStatus.OCR_READY),
        (DocumentWorkflowStatus.OCR_READY, DocumentWorkflowStatus.NEEDS_REVIEW),
        (DocumentWorkflowStatus.NEEDS_REVIEW, DocumentWorkflowStatus.VERIFIED),
        (DocumentWorkflowStatus.NEEDS_REVIEW, DocumentWorkflowStatus.INCOMPLETE),
        (DocumentWorkflowStatus.INCOMPLETE, DocumentWorkflowStatus.NEEDS_REVIEW),
        (DocumentWorkflowStatus.VERIFIED, DocumentWorkflowStatus.READY_FOR_EXPORT),
        (DocumentWorkflowStatus.READY_FOR_EXPORT, DocumentWorkflowStatus.EXPORTED),
    }
)


def can_transition_document(
    current: DocumentWorkflowStatus, target: DocumentWorkflowStatus
) -> bool:
    return (current, target) in _ALLOWED


def transition_document(document: Document, target: DocumentWorkflowStatus) -> None:
    current = document.workflow_status
    if not can_transition_document(current, target):
        raise InvalidTransitionError(f"document_transition: {current}->{target}")
    document.workflow_status = target
