from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ConfirmDocumentRegionsResult,
    ExistingRecipeSelection,
    NewRecipeRevision,
    RecipeSelection,
    RegionSetMemberInput,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.media import (
    DecodedGeometryMedia,
    GeometryDecoderPort,
    GeometryRendererPort,
)
from document_intake.application.ports.persistence import UnitOfWork, UnitOfWorkFactory
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
from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryErrorCode,
    GeometryPipelineVersion,
    ImageGeometryRecipe,
    derive_geometry_dimensions,
)
from document_intake.domain.value_objects import AuditReasonCode, AuditValueSummary, EntityId
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


class DocumentRegionsError(Exception):
    def __init__(self, code: DocumentRegionErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _fail(code: DocumentRegionErrorCode) -> NoReturn:
    raise DocumentRegionsError(code) from None


@dataclass(frozen=True, slots=True)
class _ReadContext:
    source: SourceFile
    stored: StoredArtifactRecord
    previous_set: DocumentRegionSetVersion | None
    selected: tuple[ImageGeometryRecipe, ...]


def _validate_command(command: ConfirmDocumentRegionsCommand) -> None:
    if len(command.members) not in (1, 2):
        _fail(DocumentRegionErrorCode.REGION_COUNT_INVALID)
    if tuple(m.order_index for m in command.members) != tuple(range(1, len(command.members) + 1)):
        _fail(DocumentRegionErrorCode.REGION_ORDER_INVALID)
    if len({m.region_id for m in command.members}) != len(command.members):
        _fail(DocumentRegionErrorCode.DUPLICATE_REGION)
    created = _validate_selections(command)
    if len(created) != len(set(created)):
        _fail(DocumentRegionErrorCode.IDENTITY_CONFLICT)
    _validate_region_aliases(command, created)


def _validate_selections(command: ConfirmDocumentRegionsCommand) -> list[object]:
    created: list[object] = [command.region_set_version_id, command.region_set_audit_event_id]
    for member in command.members:
        selection = member.recipe_selection
        if isinstance(selection, NewRecipeRevision):
            created.extend((selection.recipe_version_id, selection.recipe_audit_event_id))
            root = (
                selection.recipe_revision == 1
                and selection.superseded_recipe_version_id is None
                and member.region_id == selection.recipe_version_id
            )
            later = (
                selection.recipe_revision > 1
                and selection.superseded_recipe_version_id is not None
                and member.region_id != selection.recipe_version_id
            )
            if not (root or later):
                _fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)
        elif not isinstance(selection, ExistingRecipeSelection):
            _fail(DocumentRegionErrorCode.REGION_SELECTION_INVALID)
    return created


def _validate_region_aliases(command: ConfirmDocumentRegionsCommand, created: list[object]) -> None:
    for member in command.members:
        selection = member.recipe_selection
        root_alias = (
            isinstance(selection, NewRecipeRevision)
            and selection.recipe_revision == 1
            and member.region_id == selection.recipe_version_id
        )
        if member.region_id in created and not root_alias:
            _fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)


def _load_read_context(
    command: ConfirmDocumentRegionsCommand, uow: UnitOfWork
) -> tuple[SourceFile, StoredArtifactRecord, DocumentRegionSetVersion | None]:
    source = uow.source_files.get(command.source_file_id)
    if source is None:
        _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    stored = uow.stored_artifacts.get(source.original_artifact_id)
    if stored is None:
        _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    previous = None
    if command.set_revision > 1:
        if command.superseded_region_set_version_id is None:
            _fail(DocumentRegionErrorCode.REGION_SET_NOT_FOUND)
        previous = uow.document_region_sets.get(command.superseded_region_set_version_id)
        if previous is None:
            _fail(DocumentRegionErrorCode.REGION_SET_NOT_FOUND)
    return source, stored, previous


def _new_recipe(
    command: ConfirmDocumentRegionsCommand,
    source: SourceFile,
    member: RegionSetMemberInput,
    selection: NewRecipeRevision,
) -> ImageGeometryRecipe:
    region_id = member.region_id
    swapped = source.exif_orientation in {5, 6, 7, 8}
    return ImageGeometryRecipe(
        selection.recipe_version_id,
        command.source_file_id,
        selection.superseded_recipe_version_id,
        selection.recipe_revision,
        GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
        source.height if swapped else source.width,
        source.width if swapped else source.height,
        selection.quarter_turn,
        selection.quadrilateral,
        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
        command.confirmed_at,
        region_id,
    )


def _resolve_recipe_selections(
    command: ConfirmDocumentRegionsCommand, source: SourceFile, uow: UnitOfWork
) -> tuple[ImageGeometryRecipe, ...]:
    selected = []
    for member in command.members:
        selection = member.recipe_selection
        if isinstance(selection, ExistingRecipeSelection):
            recipe = uow.image_geometry_recipes.get(selection.geometry_recipe_version_id)
            if (
                recipe is None
                or recipe.source_file_id != command.source_file_id
                or recipe.region_id != member.region_id
            ):
                _fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)
        else:
            latest = uow.image_geometry_recipes.get_latest_by_region(
                command.source_file_id, member.region_id
            )
            valid_root = selection.recipe_revision == 1 and latest is None
            valid_later = (
                latest is not None
                and selection.recipe_revision == latest.revision + 1
                and selection.superseded_recipe_version_id == latest.recipe_version_id
            )
            if not (valid_root or valid_later):
                _fail(DocumentRegionErrorCode.REGION_REVISION_CONFLICT)
            recipe = _new_recipe(command, source, member, selection)
        selected.append(recipe)
    return tuple(selected)


def _validate_complete_selected_set(selected: tuple[ImageGeometryRecipe, ...]) -> None:
    recipe_ids = {recipe.recipe_version_id for recipe in selected}
    quadrilaterals = {recipe.quadrilateral for recipe in selected}
    if len(recipe_ids) != len(selected) or len(quadrilaterals) != len(selected):
        _fail(DocumentRegionErrorCode.DUPLICATE_REGION)


def _render_selected_set(
    context: _ReadContext,
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    storage: StoragePort,
) -> None:
    try:
        content = storage.read_bytes(expected=context.stored)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.ARTIFACT_INTEGRITY_FAILED) from None
    try:
        media = decoder.decode_for_geometry(content=content)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.DECODE_FAILED) from None
    expected = (
        (context.source.height, context.source.width)
        if context.source.exif_orientation in {5, 6, 7, 8}
        else (context.source.width, context.source.height)
    )
    if (media.effective_width, media.effective_height) != expected:
        raise ImageGeometryError(GeometryErrorCode.SOURCE_DIMENSIONS_MISMATCH)
    for recipe in context.selected:
        _render_recipe(recipe, media, renderer)


def _render_recipe(
    recipe: ImageGeometryRecipe, media: DecodedGeometryMedia, renderer: GeometryRendererPort
) -> None:
    try:
        recipe.quadrilateral.validate_for_source(media.effective_width, media.effective_height)
        expected = derive_geometry_dimensions(recipe.quadrilateral, recipe.quarter_turn)
        rendered = renderer.render_geometry(
            media=media,
            quadrilateral=recipe.quadrilateral,
            quarter_turn=recipe.quarter_turn,
            pipeline=recipe.pipeline,
        )
        if (rendered.width, rendered.height) != expected or rendered.pipeline != recipe.pipeline:
            raise ValueError
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None


def _revalidate_write_context(
    command: ConfirmDocumentRegionsCommand, read: _ReadContext, uow: UnitOfWork
) -> None:
    if (
        uow.source_files.get(command.source_file_id) != read.source
        or uow.stored_artifacts.get(read.source.original_artifact_id) != read.stored
    ):
        _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    latest_set = uow.document_region_sets.get_latest_by_source(command.source_file_id)
    expected_revision = 1 if latest_set is None else latest_set.revision + 1
    expected_predecessor = None if latest_set is None else latest_set.region_set_version_id
    if (
        command.set_revision != expected_revision
        or command.superseded_region_set_version_id != expected_predecessor
    ):
        _fail(DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT)
    if command.set_revision > 1:
        predecessor_id = command.superseded_region_set_version_id
        if (
            predecessor_id is None
            or uow.document_region_sets.get(predecessor_id) != read.previous_set
        ):
            _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    _verify_absent_ids(command, uow)
    for member, recipe in zip(command.members, read.selected, strict=True):
        _revalidate_recipe(command, member.recipe_selection, recipe, member.region_id, uow)


def _verify_absent_ids(command: ConfirmDocumentRegionsCommand, uow: UnitOfWork) -> None:
    if (
        uow.document_region_sets.get(command.region_set_version_id) is not None
        or uow.audit_events.get(command.region_set_audit_event_id) is not None
    ):
        _fail(DocumentRegionErrorCode.IDENTITY_CONFLICT)
    for member in command.members:
        selection = member.recipe_selection
        if isinstance(selection, NewRecipeRevision) and (
            uow.image_geometry_recipes.get(selection.recipe_version_id) is not None
            or uow.audit_events.get(selection.recipe_audit_event_id) is not None
        ):
            _fail(DocumentRegionErrorCode.IDENTITY_CONFLICT)


def _revalidate_recipe(
    command: ConfirmDocumentRegionsCommand,
    selection: RecipeSelection,
    recipe: ImageGeometryRecipe,
    region_id: EntityId,
    uow: UnitOfWork,
) -> None:
    if isinstance(selection, ExistingRecipeSelection):
        if uow.image_geometry_recipes.get(selection.geometry_recipe_version_id) != recipe:
            _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
        return
    latest = uow.image_geometry_recipes.get_latest_by_region(command.source_file_id, region_id)
    if selection.recipe_revision == 1:
        if latest is not None:
            _fail(DocumentRegionErrorCode.REGION_REVISION_CONFLICT)
    elif (
        latest is None
        or latest.recipe_version_id != selection.superseded_recipe_version_id
        or selection.recipe_revision != latest.revision + 1
    ):
        _fail(DocumentRegionErrorCode.REGION_REVISION_CONFLICT)


def _recipe_audit(
    command: ConfirmDocumentRegionsCommand, selection: NewRecipeRevision
) -> AuditEvent:
    return AuditEvent(
        selection.recipe_audit_event_id,
        command.confirmed_at,
        command.actor,
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
        selection.recipe_version_id,
        None,
        AuditValueSummary(AuditValueClassification.ABSENT, None, False),
        AuditValueSummary(AuditValueClassification.NON_SENSITIVE, "IMAGE_GEOMETRY_RECIPE", True),
        AuditReasonCode("IMAGE_GEOMETRY_RECIPE_CREATED"),
        command.correlation_id,
    )


def _set_audit(command: ConfirmDocumentRegionsCommand) -> AuditEvent:
    return AuditEvent(
        command.region_set_audit_event_id,
        command.confirmed_at,
        command.actor,
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
        AuditSubjectType.DOCUMENT_REGION_SET,
        command.region_set_version_id,
        None,
        AuditValueSummary(AuditValueClassification.ABSENT, None, False),
        AuditValueSummary(AuditValueClassification.NON_SENSITIVE, "DOCUMENT_REGION_SET", True),
        AuditReasonCode("DOCUMENT_REGION_SET_CONFIRMED"),
        command.correlation_id,
    )


def _persist_confirmation(
    command: ConfirmDocumentRegionsCommand, context: _ReadContext, uow: UnitOfWork
) -> DocumentRegionSetVersion:
    region_set = DocumentRegionSetVersion(
        command.region_set_version_id,
        command.source_file_id,
        command.superseded_region_set_version_id,
        command.set_revision,
        tuple(
            DocumentRegionSetMember(member.order_index, member.region_id, recipe.recipe_version_id)
            for member, recipe in zip(command.members, context.selected, strict=True)
        ),
        command.confirmed_at,
        command.actor,
    )
    try:
        for member, recipe in zip(command.members, context.selected, strict=True):
            if isinstance(member.recipe_selection, NewRecipeRevision):
                uow.image_geometry_recipes.add(recipe)
                uow.audit_events.add(_recipe_audit(command, member.recipe_selection))
        uow.document_region_sets.add(region_set)
        uow.audit_events.add(_set_audit(command))
    except PersistenceError as error:
        _map_controlled_failure(error, late=True)
    return region_set


def _map_controlled_failure(error: PersistenceError, *, late: bool = False) -> NoReturn:
    if error.code is PersistenceErrorCode.PERSISTED_DATA_INVALID:
        _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    if error.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS:
        _fail(
            DocumentRegionErrorCode.PERSISTENCE_CONFLICT
            if late
            else DocumentRegionErrorCode.IDENTITY_CONFLICT
        )
    _fail(DocumentRegionErrorCode.PERSISTENCE_FAILED)


def confirm_document_regions(
    command: ConfirmDocumentRegionsCommand,
    *,
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> ConfirmDocumentRegionsResult:
    _validate_command(command)
    try:
        with unit_of_work_factory.unit_of_work() as read_uow:
            source, stored, previous = _load_read_context(command, read_uow)
            selected = _resolve_recipe_selections(command, source, read_uow)
            _validate_complete_selected_set(selected)
    except PersistenceError as error:
        _map_controlled_failure(error)
    context = _ReadContext(source, stored, previous, selected)
    _render_selected_set(context, decoder, renderer, storage)
    try:
        with unit_of_work_factory.unit_of_work() as write_uow:
            _revalidate_write_context(command, context, write_uow)
            region_set = _persist_confirmation(command, context, write_uow)
            try:
                write_uow.commit()
            except Exception:
                _fail(DocumentRegionErrorCode.COMMIT_FAILED)
    except PersistenceError as error:
        _map_controlled_failure(error, late=True)
    return ConfirmDocumentRegionsResult(region_set, selected)
