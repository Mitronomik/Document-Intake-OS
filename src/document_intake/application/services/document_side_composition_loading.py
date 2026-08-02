"""Persisted side-context loading and authoritative validation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from document_intake.application.dto.document_side_composition import DocumentSideReference
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.persistence import UnitOfWork
from document_intake.application.services.document_side_composition_validation import fail
from document_intake.domain.document_regions import (
    DocumentRegionSetMember,
    DocumentRegionSetVersion,
)
from document_intake.domain.document_side_composition import DocumentSideCompositionErrorCode
from document_intake.domain.entities import SourceFile
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.image_geometry import ImageGeometryRecipe
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


@dataclass(frozen=True, slots=True)
class DocumentSideContext:
    reference: DocumentSideReference
    region_set: DocumentRegionSetVersion
    member: DocumentRegionSetMember
    recipe: ImageGeometryRecipe
    source: SourceFile
    original: StoredArtifactRecord

    def __repr__(self) -> str:
        return "DocumentSideContext(<redacted>)"


def _repository_call(operation: Callable[[], object]) -> object:
    try:
        return operation()
    except PersistenceError as error:
        if error.code is PersistenceErrorCode.PERSISTED_DATA_INVALID:
            fail(DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID)
        fail(DocumentSideCompositionErrorCode.PERSISTENCE_FAILED)
    except Exception:
        fail(DocumentSideCompositionErrorCode.PERSISTENCE_FAILED)


def _missing(code: DocumentSideCompositionErrorCode, write_phase: bool) -> None:
    fail(DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID if write_phase else code)


def load_side_context(
    uow: UnitOfWork, reference: DocumentSideReference, *, write_phase: bool = False
) -> DocumentSideContext:
    region_set = _repository_call(
        lambda: uow.document_region_sets.get(reference.region_set_version_id),
    )
    if region_set is None:
        _missing(DocumentSideCompositionErrorCode.REGION_SET_NOT_FOUND, write_phase)
    assert isinstance(region_set, DocumentRegionSetVersion)
    member = next(
        (item for item in region_set.members if item.region_id == reference.region_id), None
    )
    if member is None:
        _missing(DocumentSideCompositionErrorCode.REGION_NOT_FOUND, write_phase)
    recipe = _repository_call(
        lambda: uow.image_geometry_recipes.get(reference.geometry_recipe_version_id),
    )
    if recipe is None:
        _missing(DocumentSideCompositionErrorCode.GEOMETRY_RECIPE_NOT_FOUND, write_phase)
    source = _repository_call(lambda: uow.source_files.get(reference.source_file_id))
    if source is None:
        _missing(DocumentSideCompositionErrorCode.SOURCE_FILE_NOT_FOUND, write_phase)
    assert isinstance(source, SourceFile)
    original = _repository_call(lambda: uow.stored_artifacts.get(source.original_artifact_id))
    if original is None:
        _missing(DocumentSideCompositionErrorCode.ORIGINAL_ARTIFACT_NOT_FOUND, write_phase)
    assert isinstance(member, DocumentRegionSetMember)
    assert isinstance(recipe, ImageGeometryRecipe)
    assert isinstance(original, StoredArtifactRecord)
    context = DocumentSideContext(reference, region_set, member, recipe, source, original)
    validate_side_context(context, write_phase=write_phase)
    return context


def _selection_valid(context: DocumentSideContext) -> bool:
    ref = context.reference
    return (
        context.region_set.region_set_version_id == ref.region_set_version_id
        and context.region_set.source_file_id == ref.source_file_id
        and context.member.region_id == ref.region_id
        and context.member.geometry_recipe_version_id == ref.geometry_recipe_version_id
    )


def _lineage_valid(context: DocumentSideContext) -> bool:
    ref = context.reference
    return (
        context.recipe.recipe_version_id == ref.geometry_recipe_version_id
        and context.recipe.source_file_id == ref.source_file_id
        and context.recipe.region_id == ref.region_id
        and context.source.id == ref.source_file_id
    )


def _original_valid(context: DocumentSideContext) -> bool:
    return (
        context.original.artifact_id == context.source.original_artifact_id
        and context.original.artifact_kind is ArtifactKind.ORIGINAL
        and context.original.plaintext_length == context.source.byte_size
        and context.original.plaintext_sha256 == context.source.sha256.value
    )


def validate_side_context(context: DocumentSideContext, *, write_phase: bool) -> None:
    if _selection_valid(context) and _lineage_valid(context) and _original_valid(context):
        return
    if write_phase:
        fail(DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID)
    ref = context.reference
    if context.region_set.source_file_id != ref.source_file_id:
        fail(DocumentSideCompositionErrorCode.REGION_SELECTION_INVALID)
    if context.member.geometry_recipe_version_id != ref.geometry_recipe_version_id:
        fail(DocumentSideCompositionErrorCode.REGION_SELECTION_INVALID)
    if (
        context.recipe.source_file_id != ref.source_file_id
        or context.recipe.region_id != ref.region_id
    ):
        fail(DocumentSideCompositionErrorCode.GEOMETRY_RECIPE_INVALID)
    fail(DocumentSideCompositionErrorCode.ORIGINAL_BYTES_INVALID)


def revalidate_side_context(uow: UnitOfWork, snapshot: DocumentSideContext) -> None:
    current = load_side_context(uow, snapshot.reference, write_phase=True)
    if current != snapshot:
        fail(DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID)
    validate_side_context(current, write_phase=True)
