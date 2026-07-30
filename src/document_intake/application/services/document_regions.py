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
from document_intake.application.ports.media import GeometryDecoderPort, GeometryRendererPort
from document_intake.application.ports.persistence import UnitOfWork, UnitOfWorkFactory
from document_intake.application.ports.storage import StoragePort
from document_intake.application.services import document_region_persistence as _persistence
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
from document_intake.domain.image_geometry import (
    SourceQuadrilateral as SourceQuadrilateral,
)
from document_intake.persistence.errors import PersistenceError

DocumentRegionsError = _persistence.DocumentRegionsError
_RecipeReadSnapshot = _persistence.RecipeReadSnapshot
_WriteReadback = _persistence.WriteReadback
_apply_exif_orientation_once = _persistence.apply_exif_orientation_once
_decode_source_once = _persistence.decode_source_once
_discard_ephemeral_rasters = _persistence.discard_ephemeral_rasters
_fail = _persistence.fail
_map_controlled_failure = _persistence.map_controlled_failure
_map_geometry_validation_error = _persistence.map_geometry_validation_error
_persist_confirmation = _persistence.persist_confirmation
_read_immutable_original_bytes = _persistence.read_immutable_original_bytes
_reject_command_level_duplicates = _persistence.reject_command_level_duplicates
_render_all_selected = _persistence.render_all_selected
_reread_recipe_state = _persistence.reread_recipe_state
_validate_all_selected_geometry = _persistence.validate_all_selected_geometry
_validate_contiguous_order_indices = _persistence.validate_contiguous_order_indices
_validate_created_record_id_distinctness = _persistence.validate_created_record_id_distinctness
_validate_exactly_one_selection_form = _persistence.validate_exactly_one_selection_form
_validate_new_revision_region_identity = _persistence.validate_new_revision_region_identity
_validate_region_count = _persistence.validate_region_count
_validate_source_independent_command = _persistence.validate_source_independent_command
_verify_effective_dimensions = _persistence.verify_effective_dimensions
_verify_integrity_contract = _persistence.verify_integrity_contract


@dataclass(frozen=True, slots=True)
class _ReadContext:
    source: SourceFile
    stored: StoredArtifactRecord
    previous_set: DocumentRegionSetVersion | None
    selected: tuple[ImageGeometryRecipe, ...]
    recipe_snapshots: tuple[_RecipeReadSnapshot, ...]


def _validate_command(command: ConfirmDocumentRegionsCommand) -> None:
    _validate_source_independent_command(command)
    _validate_region_count(command)
    _validate_contiguous_order_indices(command)
    created = _validate_created_record_id_distinctness(command)
    _validate_exactly_one_selection_form(command)
    _validate_new_revision_region_identity(command, created)
    _reject_command_level_duplicates(command)


def _load_source(command: ConfirmDocumentRegionsCommand, uow: UnitOfWork) -> SourceFile:
    source = uow.source_files.get(command.source_file_id)
    if source is None:
        raise ImageGeometryError(GeometryErrorCode.SOURCE_FILE_NOT_FOUND)
    return source


def _load_original_artifact(source: SourceFile, uow: UnitOfWork) -> StoredArtifactRecord:
    stored = uow.stored_artifacts.get(source.original_artifact_id)
    if stored is None:
        raise ImageGeometryError(GeometryErrorCode.ARTIFACT_NOT_FOUND)
    return stored


def _load_preceding_set(
    command: ConfirmDocumentRegionsCommand, uow: UnitOfWork
) -> DocumentRegionSetVersion | None:
    if command.set_revision == 1:
        return None
    if command.superseded_region_set_version_id is None:
        _fail(DocumentRegionErrorCode.REGION_SET_NOT_FOUND)
    previous = uow.document_region_sets.get(command.superseded_region_set_version_id)
    if previous is None:
        _fail(DocumentRegionErrorCode.REGION_SET_NOT_FOUND)
    return previous


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
    existing = _load_selected_existing_recipes(command, uow)
    latest_by_region = _load_new_revision_state(command, uow)
    selected = []
    snapshots = []
    for member in command.members:
        selection = member.recipe_selection
        exact: ImageGeometryRecipe | None
        latest_at_read: ImageGeometryRecipe | None
        if isinstance(selection, ExistingRecipeSelection):
            recipe = existing.get(selection.geometry_recipe_version_id)
            if (
                recipe is None
                or recipe.source_file_id != command.source_file_id
                or recipe.region_id != member.region_id
            ):
                _fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)
            exact, latest_at_read = recipe, None
        else:
            latest = latest_by_region.get(member.region_id)
            valid_root = selection.recipe_revision == 1 and latest is None
            valid_later = (
                latest is not None
                and selection.recipe_revision == latest.revision + 1
                and selection.superseded_recipe_version_id == latest.recipe_version_id
            )
            if not (valid_root or valid_later):
                _fail(DocumentRegionErrorCode.REGION_REVISION_CONFLICT)
            recipe = _new_recipe(command, source, member, selection)
            exact = latest_at_read = latest
        selected.append(recipe)
        snapshots.append(_RecipeReadSnapshot(recipe, exact, latest_at_read))
    return tuple(selected), tuple(snapshots)


def _load_selected_existing_recipes(
    command: ConfirmDocumentRegionsCommand, uow: UnitOfWork
) -> dict[object, ImageGeometryRecipe | None]:
    return {
        selection.geometry_recipe_version_id: uow.image_geometry_recipes.get(
            selection.geometry_recipe_version_id
        )
        for member in command.members
        if isinstance(selection := member.recipe_selection, ExistingRecipeSelection)
    }


def _load_new_revision_state(
    command: ConfirmDocumentRegionsCommand, uow: UnitOfWork
) -> dict[object, ImageGeometryRecipe | None]:
    return {
        member.region_id: uow.image_geometry_recipes.get_latest_by_region(
            command.source_file_id, member.region_id
        )
        for member in command.members
        if isinstance(member.recipe_selection, NewRecipeRevision)
    }


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
    content = _read_immutable_original_bytes(context.stored, storage)
    _verify_integrity_contract(content)
    media = _apply_exif_orientation_once(_decode_source_once(content, decoder))
    _verify_effective_dimensions(context.source, media)
    _validate_all_selected_geometry(context.selected, media)
    dimensions = _derive_all_output_dimensions(context.selected)
    rasters = _render_all_selected(context.selected, dimensions, media, renderer)
    _discard_ephemeral_rasters(rasters, len(context.selected))


def _derive_all_output_dimensions(
    selected: tuple[ImageGeometryRecipe, ...],
) -> tuple[tuple[int, int], ...]:
    try:
        return tuple(derive_geometry_dimensions(r.quadrilateral, r.quarter_turn) for r in selected)
    except InvalidValueError as error:
        _map_geometry_validation_error(error)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None


def _revalidate_write_context(
    command: ConfirmDocumentRegionsCommand, read: _ReadContext, uow: UnitOfWork
) -> None:
    _reread_source_and_artifact(command, read, uow)
    readback = _reread_and_revalidate_selected_state(command, read, uow)
    _verify_absent_ids(command, uow)
    _verify_set_revision(command, read, readback)
    _verify_region_revisions(command, read, readback)


def _reread_source_and_artifact(
    command: ConfirmDocumentRegionsCommand, read: _ReadContext, uow: UnitOfWork
) -> None:
    if (
        uow.source_files.get(command.source_file_id) != read.source
        or uow.stored_artifacts.get(read.source.original_artifact_id) != read.stored
    ):
        _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)


def _verify_region_revisions(
    command: ConfirmDocumentRegionsCommand, read: _ReadContext, readback: _WriteReadback
) -> None:
    for member, recipe, current in zip(
        command.members, read.selected, readback.latest_recipes, strict=True
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
    exact_recipes, latest_recipes = _reread_recipe_state(command, uow)
    if previous != read.previous_set or any(
        current != snapshot.exact_persisted_recipe_at_read
        for current, snapshot in zip(exact_recipes, read.recipe_snapshots, strict=True)
    ):
        _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    return _WriteReadback(previous, latest_set, exact_recipes, latest_recipes)


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
            source = _load_source(command, read_uow)
            stored = _load_original_artifact(source, read_uow)
            previous = _load_preceding_set(command, read_uow)
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
    return _construct_confirmation_result(region_set, selected)


def _construct_confirmation_result(
    region_set: DocumentRegionSetVersion, selected: tuple[ImageGeometryRecipe, ...]
) -> ConfirmDocumentRegionsResult:
    return ConfirmDocumentRegionsResult(region_set, selected)
