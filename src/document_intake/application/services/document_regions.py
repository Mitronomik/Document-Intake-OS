from __future__ import annotations

from dataclasses import dataclass

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
from document_intake.application.services.document_region_persistence import (
    DocumentRegionsError,
)
from document_intake.application.services.document_region_persistence import (
    RecipeReadSnapshot as _RecipeReadSnapshot,
)
from document_intake.application.services.document_region_persistence import (
    WriteReadback as _WriteReadback,
)
from document_intake.application.services.document_region_persistence import (
    fail as _fail,
)
from document_intake.application.services.document_region_persistence import (
    map_controlled_failure as _map_controlled_failure,
)
from document_intake.application.services.document_region_persistence import (
    map_geometry_validation_error as _map_geometry_validation_error,
)
from document_intake.application.services.document_region_persistence import (
    persist_confirmation as _persist_confirmation,
)
from document_intake.application.services.image_geometry import ImageGeometryError
from document_intake.domain.document_regions import (
    DocumentRegionErrorCode,
    DocumentRegionSetVersion,
)
from document_intake.domain.entities import SourceFile
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryErrorCode,
    GeometryPipelineVersion,
    ImageGeometryRecipe,
    derive_geometry_dimensions,
)
from document_intake.persistence.errors import PersistenceError


@dataclass(frozen=True, slots=True)
class _ReadContext:
    source: SourceFile
    stored: StoredArtifactRecord
    previous_set: DocumentRegionSetVersion | None
    selected: tuple[ImageGeometryRecipe, ...]
    recipe_snapshots: tuple[_RecipeReadSnapshot, ...]


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
        raise ImageGeometryError(GeometryErrorCode.SOURCE_FILE_NOT_FOUND)
    stored = uow.stored_artifacts.get(source.original_artifact_id)
    if stored is None:
        raise ImageGeometryError(GeometryErrorCode.ARTIFACT_NOT_FOUND)
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
) -> tuple[tuple[ImageGeometryRecipe, ...], tuple[_RecipeReadSnapshot, ...]]:
    selected = []
    snapshots = []
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
        snapshots.append(
            _RecipeReadSnapshot(
                recipe, recipe if isinstance(selection, ExistingRecipeSelection) else latest
            )
        )
    return tuple(selected), tuple(snapshots)


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
    try:
        for recipe in context.selected:
            recipe.quadrilateral.validate_for_source(media.effective_width, media.effective_height)
    except InvalidValueError as error:
        _map_geometry_validation_error(error)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None
    try:
        dimensions = tuple(
            derive_geometry_dimensions(recipe.quadrilateral, recipe.quarter_turn)
            for recipe in context.selected
        )
    except InvalidValueError as error:
        _map_geometry_validation_error(error)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None
    for recipe, expected_dimensions in zip(context.selected, dimensions, strict=True):
        _render_recipe(recipe, media, renderer, expected_dimensions)


def _render_recipe(
    recipe: ImageGeometryRecipe,
    media: DecodedGeometryMedia,
    renderer: GeometryRendererPort,
    expected: tuple[int, int],
) -> None:
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
    readback = _reread_and_revalidate_selected_state(command, read, uow)
    _verify_absent_ids(command, uow)
    _verify_set_revision(command, read, readback)
    for member, recipe, current in zip(
        command.members, read.selected, readback.recipes, strict=True
    ):
        _verify_region_revision(member.recipe_selection, recipe, current)


def _reread_and_revalidate_selected_state(
    command: ConfirmDocumentRegionsCommand, read: _ReadContext, uow: UnitOfWork
) -> _WriteReadback:
    previous = (
        uow.document_region_sets.get(command.superseded_region_set_version_id)
        if command.superseded_region_set_version_id is not None
        else None
    )
    latest_set = uow.document_region_sets.get_latest_by_source(command.source_file_id)
    recipes = tuple(
        uow.image_geometry_recipes.get(selection.geometry_recipe_version_id)
        if isinstance(selection := member.recipe_selection, ExistingRecipeSelection)
        else uow.image_geometry_recipes.get_latest_by_region(
            command.source_file_id, member.region_id
        )
        for member in command.members
    )
    if previous != read.previous_set or any(
        current != snapshot.persisted_recipe_at_read
        for current, snapshot in zip(recipes, read.recipe_snapshots, strict=True)
    ):
        _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    return _WriteReadback(previous, latest_set, recipes)


def _verify_set_revision(
    command: ConfirmDocumentRegionsCommand, read: _ReadContext, readback: _WriteReadback
) -> None:
    latest_set = readback.latest_set
    expected_revision = 1 if latest_set is None else latest_set.revision + 1
    expected_predecessor = None if latest_set is None else latest_set.region_set_version_id
    if (
        command.set_revision != expected_revision
        or command.superseded_region_set_version_id != expected_predecessor
    ):
        _fail(DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT)
    if command.set_revision > 1:
        predecessor_id = command.superseded_region_set_version_id
        if predecessor_id is None or readback.previous_set != read.previous_set:
            _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)


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


def _verify_region_revision(
    selection: RecipeSelection,
    recipe: ImageGeometryRecipe,
    latest: ImageGeometryRecipe | None,
) -> None:
    if isinstance(selection, ExistingRecipeSelection):
        if latest != recipe:
            _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
        return
    if selection.recipe_revision == 1:
        if latest is not None:
            _fail(DocumentRegionErrorCode.REGION_REVISION_CONFLICT)
    elif (
        latest is None
        or latest.recipe_version_id != selection.superseded_recipe_version_id
        or selection.recipe_revision != latest.revision + 1
    ):
        _fail(DocumentRegionErrorCode.REGION_REVISION_CONFLICT)


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
        read_cm = unit_of_work_factory.unit_of_work()
        with read_cm as read_uow:
            source, stored, previous = _load_read_context(command, read_uow)
            selected, recipe_snapshots = _resolve_recipe_selections(command, source, read_uow)
            _validate_complete_selected_set(selected)
    except (DocumentRegionsError, ImageGeometryError):
        raise
    except PersistenceError as error:
        _map_controlled_failure(error)
    except Exception:
        _fail(DocumentRegionErrorCode.PERSISTENCE_FAILED)
    context = _ReadContext(source, stored, previous, selected, recipe_snapshots)
    _render_selected_set(context, decoder, renderer, storage)
    try:
        write_cm = unit_of_work_factory.unit_of_work()
        with write_cm as write_uow:
            _revalidate_write_context(command, context, write_uow)
            region_set = _persist_confirmation(command, context.selected, write_uow)
            try:
                write_uow.commit()
            except Exception:
                _fail(DocumentRegionErrorCode.COMMIT_FAILED)
    except DocumentRegionsError:
        raise
    except PersistenceError as error:
        _map_controlled_failure(error, late=True)
    except Exception:
        _fail(DocumentRegionErrorCode.PERSISTENCE_FAILED)
    return ConfirmDocumentRegionsResult(region_set, selected)
