"""Typed persistence and controlled-error helpers for document-region confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    NewRecipeRevision,
)
from document_intake.application.ports.persistence import UnitOfWork
from document_intake.application.services.image_geometry import ImageGeometryError
from document_intake.domain.document_regions import (
    DocumentRegionErrorCode,
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
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
