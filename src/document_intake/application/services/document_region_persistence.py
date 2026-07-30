"""Typed persistence and controlled-error helpers for document-region confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    NewRecipeRevision,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.media import (
    DecodedGeometryMedia,
    GeometryDecoderPort,
    GeometryRendererPort,
    RenderedGeometryRaster,
)
from document_intake.application.ports.persistence import UnitOfWork
from document_intake.application.ports.storage import StoragePort
from document_intake.application.services.image_geometry import ImageGeometryError
from document_intake.domain.document_regions import (
    DocumentRegionErrorCode,
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.entities import SourceFile
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import AuditAction, AuditSubjectType, AuditValueClassification
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryErrorCode,
    ImageGeometryRecipe,
)
from document_intake.domain.value_objects import AuditReasonCode, AuditValueSummary
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


class DocumentRegionsError(Exception):
    def __init__(self, code: DocumentRegionErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class RecipeReadSnapshot:
    selected_recipe: ImageGeometryRecipe
    exact_persisted_recipe_at_read: ImageGeometryRecipe | None
    latest_recipe_at_read: ImageGeometryRecipe | None


@dataclass(frozen=True, slots=True)
class WriteReadback:
    previous_set: DocumentRegionSetVersion | None
    latest_set: DocumentRegionSetVersion | None
    exact_recipes: tuple[ImageGeometryRecipe | None, ...]
    latest_recipes: tuple[ImageGeometryRecipe | None, ...]


def fail(code: DocumentRegionErrorCode) -> NoReturn:
    raise DocumentRegionsError(code) from None


def map_geometry_validation_error(error: InvalidValueError) -> NoReturn:
    try:
        code = GeometryErrorCode(str(error))
    except ValueError:
        code = GeometryErrorCode.RENDER_FAILED
    raise ImageGeometryError(code) from None


def map_controlled_failure(error: PersistenceError, *, late: bool = False) -> NoReturn:
    if error.code is PersistenceErrorCode.PERSISTED_DATA_INVALID:
        fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    if error.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS:
        fail(
            DocumentRegionErrorCode.PERSISTENCE_CONFLICT
            if late
            else DocumentRegionErrorCode.IDENTITY_CONFLICT
        )
    fail(DocumentRegionErrorCode.PERSISTENCE_FAILED)


def validate_source_independent_command(command: ConfirmDocumentRegionsCommand) -> None:
    if command.set_revision < 1:
        fail(DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT)


def validate_region_count(command: ConfirmDocumentRegionsCommand) -> None:
    if len(command.members) not in (1, 2):
        fail(DocumentRegionErrorCode.REGION_COUNT_INVALID)


def validate_contiguous_order_indices(command: ConfirmDocumentRegionsCommand) -> None:
    if tuple(member.order_index for member in command.members) != tuple(
        range(1, len(command.members) + 1)
    ):
        fail(DocumentRegionErrorCode.REGION_ORDER_INVALID)


def validate_created_record_id_distinctness(
    command: ConfirmDocumentRegionsCommand,
) -> tuple[object, ...]:
    created: list[object] = [command.region_set_version_id, command.region_set_audit_event_id]
    for member in command.members:
        if isinstance(selection := member.recipe_selection, NewRecipeRevision):
            created.extend((selection.recipe_version_id, selection.recipe_audit_event_id))
    if len(created) != len(set(created)):
        fail(DocumentRegionErrorCode.IDENTITY_CONFLICT)
    return tuple(created)


def validate_exactly_one_selection_form(command: ConfirmDocumentRegionsCommand) -> None:
    if any(
        not isinstance(member.recipe_selection, (ExistingRecipeSelection, NewRecipeRevision))
        for member in command.members
    ):
        fail(DocumentRegionErrorCode.REGION_SELECTION_INVALID)


def validate_new_revision_region_identity(
    command: ConfirmDocumentRegionsCommand, created: tuple[object, ...]
) -> None:
    for member in command.members:
        selection = member.recipe_selection
        if not isinstance(selection, NewRecipeRevision):
            continue
        root = selection.recipe_revision == 1 and selection.superseded_recipe_version_id is None
        later = selection.recipe_revision > 1 and selection.superseded_recipe_version_id is not None
        root_alias = root and member.region_id == selection.recipe_version_id
        if not (root_alias or (later and member.region_id != selection.recipe_version_id)):
            fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)
        if member.region_id in created and not root_alias:
            fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)


def reject_command_level_duplicates(command: ConfirmDocumentRegionsCommand) -> None:
    region_ids = tuple(member.region_id for member in command.members)
    existing_ids = tuple(
        selection.geometry_recipe_version_id
        for member in command.members
        if isinstance(selection := member.recipe_selection, ExistingRecipeSelection)
    )
    new_quadrilaterals = tuple(
        selection.quadrilateral
        for member in command.members
        if isinstance(selection := member.recipe_selection, NewRecipeRevision)
    )
    if any(
        len(values) != len(set(values)) for values in (region_ids, existing_ids, new_quadrilaterals)
    ):
        fail(DocumentRegionErrorCode.DUPLICATE_REGION)


def reread_recipe_state(
    command: ConfirmDocumentRegionsCommand, uow: UnitOfWork
) -> tuple[tuple[ImageGeometryRecipe | None, ...], tuple[ImageGeometryRecipe | None, ...]]:
    exact = tuple(
        uow.image_geometry_recipes.get(selection.geometry_recipe_version_id)
        if isinstance(selection := member.recipe_selection, ExistingRecipeSelection)
        else uow.image_geometry_recipes.get(selection.superseded_recipe_version_id)
        if selection.superseded_recipe_version_id is not None
        else None
        for member in command.members
    )
    latest = tuple(
        None
        if isinstance(member.recipe_selection, ExistingRecipeSelection)
        else uow.image_geometry_recipes.get_latest_by_region(
            command.source_file_id, member.region_id
        )
        for member in command.members
    )
    return exact, latest


def read_immutable_original_bytes(stored: StoredArtifactRecord, storage: StoragePort) -> bytes:
    try:
        return storage.read_bytes(expected=stored)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.ARTIFACT_INTEGRITY_FAILED) from None


def verify_integrity_contract(content: bytes) -> None:
    if type(content) is not bytes or not content:
        raise ImageGeometryError(GeometryErrorCode.ARTIFACT_INTEGRITY_FAILED)


def decode_source_once(content: bytes, decoder: GeometryDecoderPort) -> DecodedGeometryMedia:
    try:
        return decoder.decode_for_geometry(content=content)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.DECODE_FAILED) from None


def apply_exif_orientation_once(media: DecodedGeometryMedia) -> DecodedGeometryMedia:
    expected = (
        (media.encoded_height, media.encoded_width)
        if media.exif_orientation in {5, 6, 7, 8}
        else (media.encoded_width, media.encoded_height)
    )
    if (media.effective_width, media.effective_height) != expected:
        raise ImageGeometryError(GeometryErrorCode.DECODE_FAILED)
    return media


def verify_effective_dimensions(source: SourceFile, media: DecodedGeometryMedia) -> None:
    expected = (
        (source.height, source.width)
        if source.exif_orientation in {5, 6, 7, 8}
        else (source.width, source.height)
    )
    if (media.effective_width, media.effective_height) != expected:
        raise ImageGeometryError(GeometryErrorCode.SOURCE_DIMENSIONS_MISMATCH)


def validate_all_selected_geometry(
    selected: tuple[ImageGeometryRecipe, ...], media: DecodedGeometryMedia
) -> None:
    try:
        for recipe in selected:
            recipe.quadrilateral.validate_for_source(media.effective_width, media.effective_height)
    except InvalidValueError as error:
        map_geometry_validation_error(error)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None


def render_all_selected(
    selected: tuple[ImageGeometryRecipe, ...],
    dimensions: tuple[tuple[int, int], ...],
    media: DecodedGeometryMedia,
    renderer: GeometryRendererPort,
) -> tuple[RenderedGeometryRaster, ...]:
    return tuple(
        render_recipe(recipe, media, renderer, expected)
        for recipe, expected in zip(selected, dimensions, strict=True)
    )


def discard_ephemeral_rasters(
    rasters: tuple[RenderedGeometryRaster, ...], expected_count: int
) -> None:
    if len(rasters) != expected_count:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED)


def render_recipe(
    recipe: ImageGeometryRecipe,
    media: DecodedGeometryMedia,
    renderer: GeometryRendererPort,
    expected: tuple[int, int],
) -> RenderedGeometryRaster:
    try:
        rendered = renderer.render_geometry(
            media=media,
            quadrilateral=recipe.quadrilateral,
            quarter_turn=recipe.quarter_turn,
            pipeline=recipe.pipeline,
        )
        if (
            (rendered.width, rendered.height) != expected
            or rendered.pipeline != recipe.pipeline
            or len(rendered.rgb_pixels) != rendered.width * rendered.height * 3
        ):
            raise ValueError
        return rendered
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None


def _summary(label: str) -> tuple[AuditValueSummary, AuditValueSummary]:
    return AuditValueSummary(AuditValueClassification.ABSENT, None, False), AuditValueSummary(
        AuditValueClassification.NON_SENSITIVE, label, True
    )


def _recipe_audit(
    command: ConfirmDocumentRegionsCommand, selection: NewRecipeRevision
) -> AuditEvent:
    before, after = _summary("IMAGE_GEOMETRY_RECIPE")
    return AuditEvent(
        selection.recipe_audit_event_id,
        command.confirmed_at,
        command.actor,
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
        selection.recipe_version_id,
        None,
        before,
        after,
        AuditReasonCode("IMAGE_GEOMETRY_RECIPE_CREATED"),
        command.correlation_id,
    )


def _set_audit(command: ConfirmDocumentRegionsCommand) -> AuditEvent:
    before, after = _summary("DOCUMENT_REGION_SET")
    return AuditEvent(
        command.region_set_audit_event_id,
        command.confirmed_at,
        command.actor,
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
        AuditSubjectType.DOCUMENT_REGION_SET,
        command.region_set_version_id,
        None,
        before,
        after,
        AuditReasonCode("DOCUMENT_REGION_SET_CONFIRMED"),
        command.correlation_id,
    )


def persist_confirmation(
    command: ConfirmDocumentRegionsCommand,
    selected: tuple[ImageGeometryRecipe, ...],
    uow: UnitOfWork,
) -> DocumentRegionSetVersion:
    region_set = DocumentRegionSetVersion(
        command.region_set_version_id,
        command.source_file_id,
        command.superseded_region_set_version_id,
        command.set_revision,
        tuple(
            DocumentRegionSetMember(member.order_index, member.region_id, recipe.recipe_version_id)
            for member, recipe in zip(command.members, selected, strict=True)
        ),
        command.confirmed_at,
        command.actor,
    )
    try:
        add_new_geometry_recipes(command, selected, uow)
        add_recipe_audits(command, uow)
        add_region_set_version(region_set, uow)
        add_region_set_audit(command, uow)
    except PersistenceError as error:
        map_controlled_failure(error, late=True)
    return region_set


def add_new_geometry_recipes(
    command: ConfirmDocumentRegionsCommand,
    selected: tuple[ImageGeometryRecipe, ...],
    uow: UnitOfWork,
) -> None:
    for member, recipe in zip(command.members, selected, strict=True):
        if isinstance(member.recipe_selection, NewRecipeRevision):
            uow.image_geometry_recipes.add(recipe)


def add_recipe_audits(command: ConfirmDocumentRegionsCommand, uow: UnitOfWork) -> None:
    for member in command.members:
        if isinstance(member.recipe_selection, NewRecipeRevision):
            uow.audit_events.add(_recipe_audit(command, member.recipe_selection))


def add_region_set_version(region_set: DocumentRegionSetVersion, uow: UnitOfWork) -> None:
    uow.document_region_sets.add(region_set)


def add_region_set_audit(command: ConfirmDocumentRegionsCommand, uow: UnitOfWork) -> None:
    uow.audit_events.add(_set_audit(command))
