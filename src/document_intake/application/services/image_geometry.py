"""PR-010 image geometry application service."""

from __future__ import annotations

from typing import NoReturn

from document_intake.application.dto.image_geometry import (
    CreateImageGeometryRecipeCommand,
    CreateImageGeometryRecipeResult,
)
from document_intake.application.ports.media import GeometryDecoderPort, GeometryRendererPort
from document_intake.application.ports.persistence import UnitOfWorkFactory
from document_intake.application.ports.storage import StoragePort
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import AuditAction, AuditSubjectType, AuditValueClassification
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryErrorCode,
    ImageGeometryRecipe,
    derive_geometry_dimensions,
)
from document_intake.domain.value_objects import AuditReasonCode, AuditValueSummary


class ImageGeometryError(Exception):
    def __init__(self, code: GeometryErrorCode) -> None:
        if not isinstance(code, GeometryErrorCode):
            raise TypeError("image_geometry_error.code: invalid_type")
        self.code = code
        super().__init__(code.value)

    def __repr__(self) -> str:
        return f"ImageGeometryError(code={self.code.value})"


def _raise(code: GeometryErrorCode) -> NoReturn:
    raise ImageGeometryError(code) from None


def _map_validation(exc: Exception) -> NoReturn:
    if isinstance(exc, InvalidValueError):
        for code in GeometryErrorCode:
            if code.value in str(exc):
                _raise(code)
    _raise(GeometryErrorCode.RENDER_FAILED)


def create_image_geometry_recipe(
    command: CreateImageGeometryRecipeCommand,
    *,
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> CreateImageGeometryRecipeResult:
    try:
        # validate caller supplied command/pipeline before storage access
        command.quadrilateral.validate_for_source(
            command.expected_source_effective_width, command.expected_source_effective_height
        )
        derive_geometry_dimensions(command.quadrilateral, command.quarter_turn)
    except ImageGeometryError:
        raise
    except Exception as exc:
        _map_validation(exc)
    try:
        cm = unit_of_work_factory.unit_of_work()
        with cm as uow:
            try:
                source = uow.source_files.get(command.source_file_id)
            except Exception:
                _raise(GeometryErrorCode.RECIPE_PERSISTENCE_FAILED)
            if source is None:
                _raise(GeometryErrorCode.SOURCE_FILE_NOT_FOUND)
            try:
                stored = uow.stored_artifacts.get(source.original_artifact_id)
            except Exception:
                _raise(GeometryErrorCode.RECIPE_PERSISTENCE_FAILED)
            if stored is None:
                _raise(GeometryErrorCode.ARTIFACT_NOT_FOUND)
            try:
                content = storage.read_bytes(expected=stored)
            except Exception:
                _raise(GeometryErrorCode.ARTIFACT_INTEGRITY_FAILED)
            try:
                media = decoder.decode_for_geometry(content=content)
            except Exception:
                _raise(GeometryErrorCode.DECODE_FAILED)
            if (media.effective_width, media.effective_height) != (
                command.expected_source_effective_width,
                command.expected_source_effective_height,
            ):
                _raise(GeometryErrorCode.SOURCE_DIMENSIONS_MISMATCH)
            try:
                rendered = renderer.render_geometry(
                    media=media,
                    quadrilateral=command.quadrilateral,
                    quarter_turn=command.quarter_turn,
                    pipeline=command.pipeline,
                )
                expected_w, expected_h = derive_geometry_dimensions(
                    command.quadrilateral, command.quarter_turn
                )
                if (
                    rendered.width != expected_w
                    or rendered.height != expected_h
                    or rendered.pipeline != command.pipeline
                    or len(rendered.rgb_pixels) != rendered.width * rendered.height * 3
                ):
                    _raise(GeometryErrorCode.RENDER_FAILED)
            except ImageGeometryError:
                raise
            except Exception:
                _raise(GeometryErrorCode.RENDER_FAILED)
            try:
                latest = uow.image_geometry_recipes.get_latest_by_source(command.source_file_id)
            except Exception:
                _raise(GeometryErrorCode.RECIPE_PERSISTENCE_FAILED)
            if latest is None:
                if command.revision != 1 or command.superseded_recipe_version_id is not None:
                    _raise(GeometryErrorCode.REVISION_CONFLICT)
            elif (
                command.revision != latest.revision + 1
                or command.superseded_recipe_version_id != latest.recipe_version_id
            ):
                _raise(GeometryErrorCode.REVISION_CONFLICT)
            recipe = ImageGeometryRecipe(
                command.recipe_version_id,
                command.source_file_id,
                command.superseded_recipe_version_id,
                command.revision,
                GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
                media.effective_width,
                media.effective_height,
                command.quarter_turn,
                command.quadrilateral,
                command.pipeline,
                command.created_at,
            )
            try:
                uow.image_geometry_recipes.add(recipe)
            except Exception:
                _raise(GeometryErrorCode.RECIPE_PERSISTENCE_FAILED)
            try:
                uow.audit_events.add(
                    AuditEvent(
                        command.audit_event_id,
                        command.created_at,
                        command.actor,
                        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
                        AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
                        command.recipe_version_id,
                        None,
                        AuditValueSummary(AuditValueClassification.ABSENT, None, False),
                        AuditValueSummary(
                            AuditValueClassification.NON_SENSITIVE, "IMAGE_GEOMETRY_RECIPE", True
                        ),
                        AuditReasonCode("IMAGE_GEOMETRY_RECIPE_CREATED"),
                        command.correlation_id,
                    )
                )
            except Exception:
                _raise(GeometryErrorCode.AUDIT_PERSISTENCE_FAILED)
            try:
                uow.commit()
            except Exception:
                _raise(GeometryErrorCode.COMMIT_FAILED)
        return CreateImageGeometryRecipeResult(
            recipe, rendered.width, rendered.height, command.pipeline
        )
    except ImageGeometryError:
        raise
    except Exception:
        _raise(GeometryErrorCode.RECIPE_PERSISTENCE_FAILED)
