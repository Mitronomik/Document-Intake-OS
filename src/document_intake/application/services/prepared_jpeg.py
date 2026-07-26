"""PR-011 recipe-specific prepared JPEG use case."""

from __future__ import annotations

from typing import NoReturn

from document_intake.application.dto.prepared_jpeg import PrepareJpegCommand, PrepareJpegResult
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.jpeg_preparation import (
    PreparedJpegEncoderPort,
    UncompressedRgbRaster,
)
from document_intake.application.ports.media import GeometryDecoderPort, GeometryRendererPort
from document_intake.application.ports.persistence import UnitOfWork, UnitOfWorkFactory
from document_intake.application.ports.storage import StoragePort
from document_intake.domain.entities import SourceFile
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import (
    ArtifactKind,
    AuditAction,
    AuditSubjectType,
    AuditValueClassification,
    ColorSpace,
    PreparedMediaType,
)
from document_intake.domain.image_geometry import ImageGeometryRecipe, derive_geometry_dimensions
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    PREPARED_JPEG_PIPELINE_ID,
    PREPARED_JPEG_PIPELINE_VERSION,
    PreparedImageArtifact,
    PreparedJpegError,
    PreparedJpegErrorCode,
    PreparedJpegPipelineVersion,
)
from document_intake.domain.value_objects import AuditReasonCode, AuditValueSummary, EntityId
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


def _raise(code: PreparedJpegErrorCode) -> NoReturn:
    raise PreparedJpegError(code) from None


def _load(
    uow: UnitOfWork, recipe_id: EntityId
) -> tuple[ImageGeometryRecipe, SourceFile, StoredArtifactRecord]:
    try:
        recipe = uow.image_geometry_recipes.get(recipe_id)
    except Exception:
        _raise(PreparedJpegErrorCode.PERSISTENCE_FAILED)
    if recipe is None:
        _raise(PreparedJpegErrorCode.GEOMETRY_RECIPE_NOT_FOUND)
    try:
        source = uow.source_files.get(recipe.source_file_id)
    except Exception:
        _raise(PreparedJpegErrorCode.PERSISTENCE_FAILED)
    if source is None:
        _raise(PreparedJpegErrorCode.SOURCE_FILE_NOT_FOUND)
    if source.id != recipe.source_file_id:
        _raise(PreparedJpegErrorCode.PERSISTENCE_FAILED)
    try:
        original = uow.stored_artifacts.get(source.original_artifact_id)
    except Exception:
        _raise(PreparedJpegErrorCode.PERSISTENCE_FAILED)
    if original is None or original.artifact_kind is not ArtifactKind.ORIGINAL:
        _raise(PreparedJpegErrorCode.ORIGINAL_ARTIFACT_NOT_FOUND)
    if (
        original.artifact_id != source.original_artifact_id
        or original.plaintext_length != source.byte_size
        or original.plaintext_sha256 != source.sha256.value
    ):
        _raise(PreparedJpegErrorCode.ORIGINAL_BYTES_INVALID)
    return recipe, source, original


def prepare_geometry_recipe_as_jpeg(
    command: PrepareJpegCommand,
    *,
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    encoder: PreparedJpegEncoderPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> PrepareJpegResult:
    try:
        with unit_of_work_factory.unit_of_work() as read_uow:
            recipe, source, original = _load(read_uow, command.geometry_recipe_version_id)
        try:
            content = storage.read_bytes(expected=original)
        except Exception:
            _raise(PreparedJpegErrorCode.ORIGINAL_BYTES_INVALID)
        try:
            media = decoder.decode_for_geometry(content=content)
        except Exception:
            _raise(PreparedJpegErrorCode.ORIGINAL_BYTES_INVALID)
        if (media.effective_width, media.effective_height) != (
            recipe.source_effective_width,
            recipe.source_effective_height,
        ):
            _raise(PreparedJpegErrorCode.SOURCE_DIMENSIONS_MISMATCH)
        try:
            rendered = renderer.render_geometry(
                media=media,
                quadrilateral=recipe.quadrilateral,
                quarter_turn=recipe.quarter_turn,
                pipeline=recipe.pipeline,
            )
            expected_width, expected_height = derive_geometry_dimensions(
                recipe.quadrilateral, recipe.quarter_turn
            )
            if (
                rendered.width != expected_width
                or rendered.height != expected_height
                or rendered.width < 1
                or rendered.height < 1
                or rendered.pipeline != recipe.pipeline
                or len(rendered.rgb_pixels) != rendered.width * rendered.height * 3
            ):
                _raise(PreparedJpegErrorCode.GEOMETRY_RENDER_FAILED)
        except PreparedJpegError:
            raise
        except Exception:
            _raise(PreparedJpegErrorCode.GEOMETRY_RENDER_FAILED)
        try:
            encoded = encoder.encode_prepared_jpeg(
                UncompressedRgbRaster(rendered.width, rendered.height, rendered.rgb_pixels),
                pipeline=PreparedJpegPipelineVersion(),
            )
        except PreparedJpegError:
            raise
        except Exception:
            _raise(PreparedJpegErrorCode.JPEG_ENCODING_FAILED)
        artifact: PreparedImageArtifact | None = None
        published = False
        try:
            with unit_of_work_factory.unit_of_work() as uow:
                current_recipe, current_source, _ = _load(uow, command.geometry_recipe_version_id)
                if current_recipe != recipe or current_source != source:
                    _raise(PreparedJpegErrorCode.PERSISTENCE_CONFLICT)
                if (
                    uow.prepared_image_artifacts.get(command.prepared_artifact_id) is not None
                    or uow.stored_artifacts.get(command.stored_artifact_id) is not None
                    or uow.audit_events.get(command.audit_event_id) is not None
                ):
                    _raise(PreparedJpegErrorCode.IDENTITY_CONFLICT)
                if (
                    uow.prepared_image_artifacts.get_by_natural_key(
                        command.geometry_recipe_version_id,
                        PREPARED_JPEG_PIPELINE_ID,
                        PREPARED_JPEG_PIPELINE_VERSION,
                        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
                        PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
                    )
                    is not None
                ):
                    _raise(PreparedJpegErrorCode.PREPARATION_ALREADY_EXISTS)
                try:
                    record = storage.publish_bytes(
                        artifact_id=command.stored_artifact_id,
                        artifact_kind=ArtifactKind.PREPARED_JPEG,
                        plaintext=encoded.jpeg_bytes,
                        created_at=command.prepared_at,
                    )
                    published = True
                except Exception:
                    _raise(PreparedJpegErrorCode.STORAGE_PUBLICATION_FAILED)
                if (
                    record.artifact_id != command.stored_artifact_id
                    or record.artifact_kind is not ArtifactKind.PREPARED_JPEG
                    or record.object_generation != 1
                    or record.plaintext_length != encoded.byte_size
                    or record.plaintext_sha256 != encoded.sha256.value
                    or record.created_at != command.prepared_at
                ):
                    _raise(PreparedJpegErrorCode.STORAGE_PUBLICATION_FAILED)
                artifact = PreparedImageArtifact(
                    command.prepared_artifact_id,
                    source.id,
                    command.geometry_recipe_version_id,
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
                    command.prepared_at,
                    command.actor,
                )
                uow.stored_artifacts.add(record)
                uow.prepared_image_artifacts.add(artifact)
                uow.audit_events.add(
                    AuditEvent(
                        command.audit_event_id,
                        command.prepared_at,
                        command.actor,
                        AuditAction.PREPARED_JPEG_CREATED,
                        AuditSubjectType.PREPARED_IMAGE_ARTIFACT,
                        command.prepared_artifact_id,
                        None,
                        AuditValueSummary(AuditValueClassification.ABSENT, None, False),
                        AuditValueSummary(
                            AuditValueClassification.NON_SENSITIVE, "PREPARED_JPEG", True
                        ),
                        AuditReasonCode("PREPARED_JPEG_CREATED"),
                        command.correlation_id,
                    )
                )
                uow.commit()
        except PreparedJpegError:
            raise
        except PersistenceError as exc:
            if published and exc.code in {
                PersistenceErrorCode.ENTITY_ALREADY_EXISTS,
                PersistenceErrorCode.PERSISTENCE_CONSTRAINT,
            }:
                _raise(PreparedJpegErrorCode.PERSISTENCE_CONFLICT)
            _raise(PreparedJpegErrorCode.PERSISTENCE_FAILED)
        except Exception:
            _raise(PreparedJpegErrorCode.PERSISTENCE_FAILED)
        if artifact is None:
            _raise(PreparedJpegErrorCode.PERSISTENCE_FAILED)
        return PrepareJpegResult(artifact)
    except PreparedJpegError:
        raise
    except Exception:
        _raise(PreparedJpegErrorCode.PERSISTENCE_FAILED)
