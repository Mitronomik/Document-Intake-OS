"""Source-independent PR-013 command validation."""

from __future__ import annotations

from typing import NoReturn

from document_intake.application.dto.document_side_composition import (
    CreateDocumentSideCompositionCommand,
)
from document_intake.domain.document_side_composition import (
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
)


def fail(code: DocumentSideCompositionErrorCode) -> NoReturn:
    raise DocumentSideCompositionError(code) from None


def validate_composition_command(command: CreateDocumentSideCompositionCommand) -> None:
    if not isinstance(command, CreateDocumentSideCompositionCommand):
        fail(DocumentSideCompositionErrorCode.COMPOSITION_INPUT_COUNT_INVALID)
    ids = (
        command.composition_id,
        command.composition_version_id,
        command.prepared_artifact_id,
        command.stored_artifact_id,
        command.audit_event_id,
    )
    if len(set(ids)) != len(ids):
        fail(DocumentSideCompositionErrorCode.IDENTITY_CONFLICT)
    if (command.side_1.source_file_id, command.side_1.region_id) == (
        command.side_2.source_file_id,
        command.side_2.region_id,
    ):
        fail(DocumentSideCompositionErrorCode.COMPOSITION_INPUT_DUPLICATE)
