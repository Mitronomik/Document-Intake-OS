"""PR-013 preflight, publication, record construction, and insertion."""

from __future__ import annotations

from document_intake.application.dto.document_side_composition import (
    CreateDocumentSideCompositionCommand,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.jpeg_preparation import EncodedPreparedJpeg
from document_intake.application.ports.persistence import UnitOfWork
from document_intake.application.ports.storage import StoragePort
from document_intake.application.services.document_side_composition_validation import fail
from document_intake.domain.document_side_composition import (
    DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID,
    DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION,
    DocumentSideComposition,
    DocumentSideCompositionErrorCode,
    DocumentSideCompositionVersion,
    PreparedCompositionArtifact,
)
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import (
    ArtifactKind,
    AuditAction,
    AuditSubjectType,
    ColorSpace,
    PreparedMediaType,
)
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    PREPARED_JPEG_PIPELINE_ID,
    PREPARED_JPEG_PIPELINE_VERSION,
)
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


def preflight(command: CreateDocumentSideCompositionCommand, uow: UnitOfWork) -> None:
    try:
        conflict = any(
            (
                uow.document_side_compositions.get_composition(command.composition_id),
                uow.document_side_compositions.get_version(command.composition_version_id),
                uow.document_side_compositions.get_artifact(command.prepared_artifact_id),
                uow.stored_artifacts.get(command.stored_artifact_id),
                uow.audit_events.get(command.audit_event_id),
            )
        )
        if conflict:
            fail(DocumentSideCompositionErrorCode.IDENTITY_CONFLICT)
        if (
            uow.document_side_compositions.get_by_natural_key(
                side_1_region_set_version_id=command.side_1.region_set_version_id,
                side_1_source_file_id=command.side_1.source_file_id,
                side_1_region_id=command.side_1.region_id,
                side_1_geometry_recipe_version_id=command.side_1.geometry_recipe_version_id,
                side_2_region_set_version_id=command.side_2.region_set_version_id,
                side_2_source_file_id=command.side_2.source_file_id,
                side_2_region_id=command.side_2.region_id,
                side_2_geometry_recipe_version_id=command.side_2.geometry_recipe_version_id,
                layout=command.layout,
                outer_margin_px=command.outer_margin_px,
                inter_side_gap_px=command.inter_side_gap_px,
                composition_pipeline_id=DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID,
                composition_pipeline_version=DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION,
                jpeg_pipeline_id=PREPARED_JPEG_PIPELINE_ID,
                jpeg_pipeline_version=PREPARED_JPEG_PIPELINE_VERSION,
                output_contract_id=PREPARED_JPEG_OUTPUT_CONTRACT_ID,
                output_contract_version=PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
            )
            is not None
        ):
            fail(DocumentSideCompositionErrorCode.COMPOSITION_ALREADY_EXISTS)
    except PersistenceError as error:
        if error.code is PersistenceErrorCode.PERSISTED_DATA_INVALID:
            fail(DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID)
        fail(DocumentSideCompositionErrorCode.PERSISTENCE_FAILED)


def publish_encoded(
    command: CreateDocumentSideCompositionCommand,
    encoded: EncodedPreparedJpeg,
    storage: StoragePort,
) -> StoredArtifactRecord:
    try:
        record = storage.publish_bytes(
            artifact_id=command.stored_artifact_id,
            artifact_kind=ArtifactKind.PREPARED_JPEG,
            plaintext=encoded.jpeg_bytes,
            created_at=command.created_at,
        )
    except Exception:
        fail(DocumentSideCompositionErrorCode.STORAGE_PUBLICATION_FAILED)
    if (
        record.artifact_id != command.stored_artifact_id
        or record.artifact_kind is not ArtifactKind.PREPARED_JPEG
        or record.object_generation != 1
        or record.plaintext_length != encoded.byte_size
        or record.plaintext_sha256 != encoded.sha256.value
        or record.created_at != command.created_at
    ):
        fail(DocumentSideCompositionErrorCode.STORAGE_PUBLICATION_FAILED)
    return record


def _build_version(
    command: CreateDocumentSideCompositionCommand,
) -> DocumentSideCompositionVersion:
    return DocumentSideCompositionVersion(
        command.composition_version_id,
        command.composition_id,
        command.side_1.region_set_version_id,
        command.side_1.source_file_id,
        command.side_1.region_id,
        command.side_1.geometry_recipe_version_id,
        command.side_2.region_set_version_id,
        command.side_2.source_file_id,
        command.side_2.region_id,
        command.side_2.geometry_recipe_version_id,
        command.layout,
        command.outer_margin_px,
        command.inter_side_gap_px,
        DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID,
        DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION,
        PREPARED_JPEG_PIPELINE_ID,
        PREPARED_JPEG_PIPELINE_VERSION,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
        command.created_at,
        command.actor,
        command.correlation_id,
    )


def _build_artifact(
    command: CreateDocumentSideCompositionCommand, encoded: EncodedPreparedJpeg
) -> PreparedCompositionArtifact:
    return PreparedCompositionArtifact(
        command.prepared_artifact_id,
        command.composition_version_id,
        command.stored_artifact_id,
        encoded.pipeline_id,
        encoded.pipeline_version,
        encoded.output_contract_id,
        encoded.output_contract_version,
        PreparedMediaType.JPEG,
        ColorSpace.SRGB,
        encoded.width,
        encoded.height,
        encoded.byte_size,
        encoded.sha256,
        encoded.jpeg_quality,
        encoded.resize_percent,
        command.created_at,
        command.actor,
    )


def _build_audit(command: CreateDocumentSideCompositionCommand) -> AuditEvent:
    return AuditEvent(
        event_id=command.audit_event_id,
        occurred_at=command.created_at,
        actor=command.actor,
        action_code=AuditAction.DOCUMENT_SIDE_COMPOSITION_CREATED,
        subject_type=AuditSubjectType.DOCUMENT_SIDE_COMPOSITION,
        subject_id=command.composition_id,
        field_key=None,
        before=None,
        after=None,
        reason_code=None,
        correlation_id=command.correlation_id,
    )


def build_records(
    command: CreateDocumentSideCompositionCommand, encoded: EncodedPreparedJpeg
) -> tuple[
    DocumentSideComposition,
    DocumentSideCompositionVersion,
    PreparedCompositionArtifact,
    AuditEvent,
]:
    expected = (
        PREPARED_JPEG_PIPELINE_ID,
        PREPARED_JPEG_PIPELINE_VERSION,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    )
    if (
        encoded.pipeline_id,
        encoded.pipeline_version,
        encoded.output_contract_id,
        encoded.output_contract_version,
    ) != expected:
        fail(DocumentSideCompositionErrorCode.JPEG_ENCODING_FAILED)
    composition = DocumentSideComposition(command.composition_id)
    version = _build_version(command)
    artifact = _build_artifact(command, encoded)
    if (
        artifact.pipeline_id != version.jpeg_pipeline_id
        or artifact.pipeline_version != version.jpeg_pipeline_version
        or artifact.output_contract_id != version.output_contract_id
        or artifact.output_contract_version != version.output_contract_version
    ):
        fail(DocumentSideCompositionErrorCode.JPEG_ENCODING_FAILED)
    audit = _build_audit(command)
    return composition, version, artifact, audit


def add_records(
    uow: UnitOfWork,
    record: StoredArtifactRecord,
    composition: DocumentSideComposition,
    version: DocumentSideCompositionVersion,
    artifact: PreparedCompositionArtifact,
    audit: AuditEvent,
) -> None:
    try:
        uow.stored_artifacts.add(record)
        uow.document_side_compositions.add_composition(composition)
        uow.document_side_compositions.add_version(version)
        uow.document_side_compositions.add_artifact(artifact)
        uow.audit_events.add(audit)
    except PersistenceError as error:
        if error.code in {
            PersistenceErrorCode.ENTITY_ALREADY_EXISTS,
            PersistenceErrorCode.PERSISTENCE_CONSTRAINT,
        }:
            fail(DocumentSideCompositionErrorCode.PERSISTENCE_CONFLICT)
        if error.code is PersistenceErrorCode.PERSISTED_DATA_INVALID:
            fail(DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID)
        fail(DocumentSideCompositionErrorCode.PERSISTENCE_FAILED)
    except Exception:
        fail(DocumentSideCompositionErrorCode.PERSISTENCE_FAILED)
