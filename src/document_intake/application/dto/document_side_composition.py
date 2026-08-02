"""Byte-free command and result DTOs for document-side composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from document_intake.domain.document_side_composition import (
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
    DocumentSideCompositionVersion,
    PreparedCompositionArtifact,
)
from document_intake.domain.enums import DocumentSideCompositionLayout
from document_intake.domain.value_objects import ActorRef, EntityId


def _fail(code: DocumentSideCompositionErrorCode) -> None:
    raise DocumentSideCompositionError(code) from None


def _validate_ids(command: CreateDocumentSideCompositionCommand) -> None:
    ids = (
        command.composition_id,
        command.composition_version_id,
        command.prepared_artifact_id,
        command.stored_artifact_id,
        command.audit_event_id,
    )
    if not all(isinstance(value, EntityId) for value in (*ids, command.correlation_id)):
        _fail(DocumentSideCompositionErrorCode.IDENTITY_CONFLICT)
    if len(set(ids)) != len(ids):
        _fail(DocumentSideCompositionErrorCode.IDENTITY_CONFLICT)


def _validate_sides(command: CreateDocumentSideCompositionCommand) -> None:
    if not isinstance(command.side_1, DocumentSideReference) or not isinstance(
        command.side_2, DocumentSideReference
    ):
        _fail(DocumentSideCompositionErrorCode.COMPOSITION_INPUT_COUNT_INVALID)
    if (command.side_1.source_file_id, command.side_1.region_id) == (
        command.side_2.source_file_id,
        command.side_2.region_id,
    ):
        _fail(DocumentSideCompositionErrorCode.COMPOSITION_INPUT_DUPLICATE)


def _validate_parameters(command: CreateDocumentSideCompositionCommand) -> None:
    if not isinstance(command.layout, DocumentSideCompositionLayout):
        _fail(DocumentSideCompositionErrorCode.COMPOSITION_LAYOUT_INVALID)
    if type(command.outer_margin_px) is not int or not 0 <= command.outer_margin_px <= 256:
        _fail(DocumentSideCompositionErrorCode.COMPOSITION_MARGIN_INVALID)
    if type(command.inter_side_gap_px) is not int or not 0 <= command.inter_side_gap_px <= 256:
        _fail(DocumentSideCompositionErrorCode.COMPOSITION_GAP_INVALID)


def _validate_context(command: CreateDocumentSideCompositionCommand) -> None:
    if (
        not isinstance(command.created_at, datetime)
        or command.created_at.tzinfo is None
        or command.created_at.utcoffset() != UTC.utcoffset(command.created_at)
    ):
        _fail(DocumentSideCompositionErrorCode.COMPOSITION_ORDER_INVALID)
    if not isinstance(command.actor, ActorRef):
        _fail(DocumentSideCompositionErrorCode.COMPOSITION_ORDER_INVALID)


@dataclass(frozen=True, slots=True)
class DocumentSideReference:
    region_set_version_id: EntityId
    source_file_id: EntityId
    region_id: EntityId
    geometry_recipe_version_id: EntityId

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, EntityId)
            for value in (
                self.region_set_version_id,
                self.source_file_id,
                self.region_id,
                self.geometry_recipe_version_id,
            )
        ):
            _fail(DocumentSideCompositionErrorCode.COMPOSITION_ORDER_INVALID)

    def __repr__(self) -> str:
        return "DocumentSideReference(<redacted>)"


@dataclass(frozen=True, slots=True)
class CreateDocumentSideCompositionCommand:
    composition_id: EntityId
    composition_version_id: EntityId
    side_1: DocumentSideReference
    side_2: DocumentSideReference
    layout: DocumentSideCompositionLayout
    outer_margin_px: int
    inter_side_gap_px: int
    prepared_artifact_id: EntityId
    stored_artifact_id: EntityId
    audit_event_id: EntityId
    created_at: datetime
    actor: ActorRef
    correlation_id: EntityId

    def __post_init__(self) -> None:
        _validate_ids(self)
        _validate_sides(self)
        _validate_parameters(self)
        _validate_context(self)

    def __repr__(self) -> str:
        return "CreateDocumentSideCompositionCommand(<redacted>)"


@dataclass(frozen=True, slots=True)
class CreateDocumentSideCompositionResult:
    composition_version: DocumentSideCompositionVersion
    artifact: PreparedCompositionArtifact

    def __repr__(self) -> str:
        return "CreateDocumentSideCompositionResult(<redacted>)"
