"""Atomic confirmation of one or two deterministic document regions."""

from __future__ import annotations

from typing import NoReturn

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ConfirmDocumentRegionsResult,
    ExistingRecipeSelection,
    NewRecipeRevision,
)
from document_intake.application.ports.media import GeometryDecoderPort, GeometryRendererPort
from document_intake.application.ports.persistence import UnitOfWorkFactory
from document_intake.application.ports.storage import StoragePort
from document_intake.domain.document_regions import (
    DocumentRegionErrorCode,
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.entities.audit import AuditEvent
from document_intake.domain.enums import AuditAction, AuditSubjectType, AuditValueClassification
from document_intake.domain.image_geometry import (
    GeometryCoordinateSpace,
    GeometryPipelineVersion,
    ImageGeometryRecipe,
    derive_geometry_dimensions,
)
from document_intake.domain.value_objects import AuditReasonCode, AuditValueSummary


class DocumentRegionsError(Exception):
    def __init__(self, code: DocumentRegionErrorCode) -> None:
        self.code = code
        super().__init__(code.value)

    def __repr__(self) -> str:
        return f"DocumentRegionsError(code={self.code.value})"


def _fail(code: DocumentRegionErrorCode) -> NoReturn:
    raise DocumentRegionsError(code) from None


def _validate(command: ConfirmDocumentRegionsCommand) -> None:
    if len(command.members) not in (1, 2):
        _fail(DocumentRegionErrorCode.REGION_COUNT_INVALID)
    if tuple(m.order_index for m in command.members) != tuple(range(1, len(command.members) + 1)):
        _fail(DocumentRegionErrorCode.REGION_ORDER_INVALID)
    if len({m.region_id for m in command.members}) != len(command.members):
        _fail(DocumentRegionErrorCode.DUPLICATE_REGION)
    created = [command.region_set_version_id, command.region_set_audit_event_id]
    selections = []
    quads = []
    for member in command.members:
        selection = member.recipe_selection
        if isinstance(selection, ExistingRecipeSelection):
            selections.append(selection.geometry_recipe_version_id)
        elif isinstance(selection, NewRecipeRevision):
            created += [selection.recipe_version_id, selection.recipe_audit_event_id]
            selections.append(selection.recipe_version_id)
            quads.append(selection.quadrilateral)
            if selection.recipe_revision == 1:
                if (
                    selection.superseded_recipe_version_id is not None
                    or member.region_id != selection.recipe_version_id
                ):
                    _fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)
            elif (
                selection.recipe_revision < 2
                or selection.superseded_recipe_version_id is None
                or member.region_id == selection.recipe_version_id
            ):
                _fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)
        else:
            _fail(DocumentRegionErrorCode.REGION_SELECTION_INVALID)
    if len(set(created)) != len(created):
        _fail(DocumentRegionErrorCode.IDENTITY_CONFLICT)
    if len(set(selections)) != len(selections) or len(set(quads)) != len(quads):
        _fail(DocumentRegionErrorCode.DUPLICATE_REGION)
    unrelated = set(created)
    for m in command.members:
        if m.region_id in unrelated and not (
            isinstance(m.recipe_selection, NewRecipeRevision)
            and m.recipe_selection.recipe_revision == 1
            and m.region_id == m.recipe_selection.recipe_version_id
        ):
            _fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)


def confirm_document_regions(
    command: ConfirmDocumentRegionsCommand,
    *,
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> ConfirmDocumentRegionsResult:
    _validate(command)
    try:
        with unit_of_work_factory.unit_of_work() as read:
            source = read.source_files.get(command.source_file_id)
            if source is None:
                _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
            stored = read.stored_artifacts.get(source.original_artifact_id)
            if stored is None:
                _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
            previous = None
            if command.set_revision > 1:
                predecessor_id = command.superseded_region_set_version_id
                if predecessor_id is None:
                    _fail(DocumentRegionErrorCode.REGION_SET_NOT_FOUND)
                previous = read.document_region_sets.get(predecessor_id)
            if command.set_revision > 1 and previous is None:
                _fail(DocumentRegionErrorCode.REGION_SET_NOT_FOUND)
            selected = []
            for member in command.members:
                sel = member.recipe_selection
                if isinstance(sel, ExistingRecipeSelection):
                    recipe = read.image_geometry_recipes.get(sel.geometry_recipe_version_id)
                    if (
                        recipe is None
                        or recipe.source_file_id != command.source_file_id
                        or recipe.region_id != member.region_id
                    ):
                        _fail(DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT)
                else:
                    latest = read.image_geometry_recipes.get_latest_by_region(
                        command.source_file_id, member.region_id
                    )
                    if sel.recipe_revision == 1:
                        if latest is not None:
                            _fail(DocumentRegionErrorCode.REGION_REVISION_CONFLICT)
                    elif (
                        latest is None
                        or sel.recipe_revision != latest.revision + 1
                        or sel.superseded_recipe_version_id != latest.recipe_version_id
                    ):
                        _fail(DocumentRegionErrorCode.REGION_REVISION_CONFLICT)
                    recipe = ImageGeometryRecipe(
                        sel.recipe_version_id,
                        command.source_file_id,
                        sel.superseded_recipe_version_id,
                        sel.recipe_revision,
                        GeometryCoordinateSpace.SOURCE_EFFECTIVE_PIXELS_V1,
                        source.height if source.exif_orientation in {5, 6, 7, 8} else source.width,
                        source.width if source.exif_orientation in {5, 6, 7, 8} else source.height,
                        sel.quarter_turn,
                        sel.quadrilateral,
                        GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1),
                        command.confirmed_at,
                        member.region_id,
                    )
                selected.append(recipe)
        assert source is not None and stored is not None
        content = storage.read_bytes(expected=stored)
        media = decoder.decode_for_geometry(content=content)
        expected = (
            (source.height, source.width)
            if source.exif_orientation in {5, 6, 7, 8}
            else (source.width, source.height)
        )
        if (media.effective_width, media.effective_height) != expected:
            _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
        for recipe in selected:
            recipe.quadrilateral.validate_for_source(media.effective_width, media.effective_height)
            dims = derive_geometry_dimensions(recipe.quadrilateral, recipe.quarter_turn)
            raster = renderer.render_geometry(
                media=media,
                quadrilateral=recipe.quadrilateral,
                quarter_turn=recipe.quarter_turn,
                pipeline=recipe.pipeline,
            )
            if (raster.width, raster.height) != dims or raster.pipeline != recipe.pipeline:
                _fail(DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
        region_set = DocumentRegionSetVersion(
            command.region_set_version_id,
            command.source_file_id,
            command.superseded_region_set_version_id,
            command.set_revision,
            tuple(
                DocumentRegionSetMember(m.order_index, m.region_id, r.recipe_version_id)
                for m, r in zip(command.members, selected, strict=True)
            ),
            command.confirmed_at,
            command.actor,
        )
        with unit_of_work_factory.unit_of_work() as write:
            latest_set = write.document_region_sets.get_latest_by_source(command.source_file_id)
            if (latest_set is None and command.set_revision != 1) or (
                latest_set is not None
                and (
                    command.set_revision != latest_set.revision + 1
                    or command.superseded_region_set_version_id != latest_set.region_set_version_id
                )
            ):
                _fail(DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT)
            for member, recipe in zip(command.members, selected, strict=True):
                if isinstance(member.recipe_selection, NewRecipeRevision):
                    write.image_geometry_recipes.add(recipe)
                    write.audit_events.add(
                        AuditEvent(
                            member.recipe_selection.recipe_audit_event_id,
                            command.confirmed_at,
                            command.actor,
                            AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
                            AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
                            recipe.recipe_version_id,
                            None,
                            AuditValueSummary(AuditValueClassification.ABSENT, None, False),
                            AuditValueSummary(
                                AuditValueClassification.NON_SENSITIVE,
                                "IMAGE_GEOMETRY_RECIPE",
                                True,
                            ),
                            AuditReasonCode("IMAGE_GEOMETRY_RECIPE_CREATED"),
                            command.correlation_id,
                        )
                    )
            write.document_region_sets.add(region_set)
            write.audit_events.add(
                AuditEvent(
                    command.region_set_audit_event_id,
                    command.confirmed_at,
                    command.actor,
                    AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
                    AuditSubjectType.DOCUMENT_REGION_SET,
                    command.region_set_version_id,
                    None,
                    AuditValueSummary(AuditValueClassification.ABSENT, None, False),
                    AuditValueSummary(
                        AuditValueClassification.NON_SENSITIVE, "DOCUMENT_REGION_SET", True
                    ),
                    AuditReasonCode("DOCUMENT_REGION_SET_CONFIRMED"),
                    command.correlation_id,
                )
            )
            write.commit()
        return ConfirmDocumentRegionsResult(region_set, tuple(selected))
    except DocumentRegionsError:
        raise
    except Exception:
        _fail(DocumentRegionErrorCode.PERSISTENCE_FAILED)
