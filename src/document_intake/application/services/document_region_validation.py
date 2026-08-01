"""Source-independent validation for document-region confirmation commands."""

from __future__ import annotations

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    NewRecipeRevision,
)
from document_intake.application.services.document_region_persistence import fail
from document_intake.domain.document_regions import DocumentRegionErrorCode


def validate_source_independent_command(command: ConfirmDocumentRegionsCommand) -> None:
    if (command.set_revision == 1) != (command.superseded_region_set_version_id is None):
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
        root_alias = False
        if isinstance(selection, NewRecipeRevision):
            root = selection.recipe_revision == 1 and selection.superseded_recipe_version_id is None
            later = (
                selection.recipe_revision > 1 and selection.superseded_recipe_version_id is not None
            )
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
