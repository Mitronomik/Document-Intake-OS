from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    NewRecipeRevision,
    RegionSetMemberInput,
)
from document_intake.application.services import document_regions as service
from document_intake.application.services.document_regions import DocumentRegionsError
from document_intake.domain.document_regions import DocumentRegionErrorCode
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import GeometryQuarterTurn
from tests.support.pr011 import entity_id, valid_geometry_recipe, valid_source_file
from tests.support.pr012_application import (
    Decoder,
    Factory,
    Renderer,
    Repo,
    Storage,
    command,
    new_selection,
    run,
    with_previous,
)

PRIVATE = "private-phase4a-marker"


def _valid_new() -> NewRecipeRevision:
    recipe = valid_geometry_recipe()
    return new_selection(entity_id(31), entity_id(41), recipe.quadrilateral)


def _valid_member() -> RegionSetMemberInput:
    recipe = valid_geometry_recipe()
    return RegionSetMemberInput(
        1, recipe.region_id, ExistingRecipeSelection(recipe.recipe_version_id)
    )


def _valid_command() -> ConfirmDocumentRegionsCommand:
    return command(valid_geometry_recipe())


@dataclass(frozen=True, slots=True)
class DtoCase:
    build: Callable[[], object]
    message: str
    private_value: str


DTO_CASES = (
    DtoCase(
        lambda: ExistingRecipeSelection(PRIVATE),
        "geometry_recipe_version_id: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_new(), recipe_version_id=PRIVATE),
        "recipe_version_id: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_new(), superseded_recipe_version_id=PRIVATE),
        "superseded_recipe_version_id: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_new(), recipe_revision=True), "recipe_revision: invalid_type", "True"
    ),
    DtoCase(
        lambda: replace(_valid_new(), recipe_revision=0), "recipe_revision: invalid_value", "0"
    ),
    DtoCase(
        lambda: replace(_valid_new(), quadrilateral=PRIVATE), "quadrilateral: invalid_type", PRIVATE
    ),
    DtoCase(
        lambda: replace(_valid_new(), quarter_turn=PRIVATE), "quarter_turn: invalid_type", PRIVATE
    ),
    DtoCase(
        lambda: replace(_valid_new(), recipe_audit_event_id=PRIVATE),
        "recipe_audit_event_id: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_member(), order_index=True), "order_index: invalid_type", "True"
    ),
    DtoCase(
        lambda: replace(_valid_member(), region_id=PRIVATE), "region_id: invalid_type", PRIVATE
    ),
    DtoCase(
        lambda: replace(_valid_member(), recipe_selection=SimpleNamespace(value=PRIVATE)),
        "recipe_selection: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_command(), region_set_version_id=PRIVATE),
        "region_set_version_id: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_command(), source_file_id=PRIVATE),
        "source_file_id: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_command(), superseded_region_set_version_id=PRIVATE),
        "superseded_region_set_version_id: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_command(), set_revision=True), "set_revision: invalid_type", "True"
    ),
    DtoCase(lambda: replace(_valid_command(), set_revision=0), "set_revision: invalid_value", "0"),
    DtoCase(
        lambda: replace(_valid_command(), members=[SimpleNamespace(value=PRIVATE)]),
        "members: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_command(), members=(SimpleNamespace(value=PRIVATE),)),
        "members: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_command(), region_set_audit_event_id=PRIVATE),
        "region_set_audit_event_id: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_command(), confirmed_at=PRIVATE),
        "confirmed_at: invalid_type",
        PRIVATE,
    ),
    DtoCase(
        lambda: replace(_valid_command(), confirmed_at=datetime(2030, 1, 2, 3, 4, 5)),
        "confirmed_at: timezone_aware_required",
        "2030-01-02",
    ),
    DtoCase(
        lambda: replace(
            _valid_command(),
            confirmed_at=datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=3))),
        ),
        "confirmed_at: must_be_utc",
        "+03:00",
    ),
    DtoCase(lambda: replace(_valid_command(), actor=PRIVATE), "actor: invalid_type", PRIVATE),
    DtoCase(
        lambda: replace(_valid_command(), correlation_id=PRIVATE),
        "correlation_id: invalid_type",
        PRIVATE,
    ),
)


@pytest.mark.parametrize("case", DTO_CASES, ids=lambda case: case.message)
def test_dto_runtime_structure_is_private_and_field_only(case: DtoCase) -> None:
    with pytest.raises(InvalidValueError) as caught:
        case.build()
    assert str(caught.value) == case.message
    assert case.private_value not in str(caught.value)
    assert case.private_value not in repr(caught.value)


def test_valid_dto_values_retain_exact_runtime_types() -> None:
    value = _valid_command()
    assert value.confirmed_at.tzinfo is UTC
    assert isinstance(value.members, tuple)
    assert isinstance(value.members[0].recipe_selection, ExistingRecipeSelection)
    assert isinstance(_valid_new().quarter_turn, GeometryQuarterTurn)


def _three_member_command() -> ConfirmDocumentRegionsCommand:
    value = _valid_command()
    return replace(
        value,
        members=tuple(
            RegionSetMemberInput(
                index, entity_id(30 + index), ExistingRecipeSelection(entity_id(40 + index))
            )
            for index in (1, 2, 3)
        ),
    )


def _invalid_selection_command() -> ConfirmDocumentRegionsCommand:
    value = _valid_command()
    member = value.members[0]
    object.__setattr__(member, "recipe_selection", SimpleNamespace(value=PRIVATE))
    return replace(value, members=(member,))


def _mutated_zero_revision_command() -> ConfirmDocumentRegionsCommand:
    value = _valid_command()
    object.__setattr__(value, "set_revision", 0)
    return value


def _two_existing_command() -> ConfirmDocumentRegionsCommand:
    first = valid_geometry_recipe()
    return replace(
        command(first),
        members=(
            RegionSetMemberInput(1, entity_id(31), ExistingRecipeSelection(entity_id(41))),
            RegionSetMemberInput(2, entity_id(32), ExistingRecipeSelection(entity_id(42))),
        ),
    )


def _two_new_command() -> ConfirmDocumentRegionsCommand:
    template = valid_geometry_recipe()
    second_quad = replace(
        template.quadrilateral,
        top_left=replace(template.quadrilateral.top_left, x=1),
    )
    return replace(
        command(template),
        members=(
            RegionSetMemberInput(
                1,
                entity_id(31),
                new_selection(entity_id(31), entity_id(41), template.quadrilateral),
            ),
            RegionSetMemberInput(
                2,
                entity_id(32),
                new_selection(entity_id(32), entity_id(42), second_quad),
            ),
        ),
    )


def _root_identity_invalid() -> ConfirmDocumentRegionsCommand:
    value = _valid_command()
    selection = _valid_new()
    return replace(
        value,
        members=(RegionSetMemberInput(1, entity_id(32), selection),),
    )


def _later_identity_invalid() -> ConfirmDocumentRegionsCommand:
    recipe = valid_geometry_recipe()
    selection = new_selection(
        entity_id(31),
        entity_id(41),
        recipe.quadrilateral,
        revision=2,
        predecessor=recipe.recipe_version_id,
    )
    return replace(command(recipe), members=(RegionSetMemberInput(1, entity_id(31), selection),))


def _duplicate_existing_selection() -> ConfirmDocumentRegionsCommand:
    value = _two_existing_command()
    selected = value.members[0].recipe_selection
    return replace(
        value, members=(value.members[0], replace(value.members[1], recipe_selection=selected))
    )


def _duplicate_new_quadrilateral() -> ConfirmDocumentRegionsCommand:
    value = _two_new_command()
    second = value.members[1].recipe_selection
    first = value.members[0].recipe_selection
    assert isinstance(first, NewRecipeRevision) and isinstance(second, NewRecipeRevision)
    return replace(
        value,
        members=(
            value.members[0],
            replace(
                value.members[1],
                recipe_selection=replace(second, quadrilateral=first.quadrilateral),
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class SemanticCase:
    build: Callable[[], ConfirmDocumentRegionsCommand]
    code: DocumentRegionErrorCode


SEMANTIC_CASES = (
    SemanticCase(
        _mutated_zero_revision_command, DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT
    ),
    SemanticCase(
        lambda: replace(_valid_command(), superseded_region_set_version_id=entity_id(99)),
        DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT,
    ),
    SemanticCase(
        lambda: replace(_valid_command(), members=()), DocumentRegionErrorCode.REGION_COUNT_INVALID
    ),
    SemanticCase(_three_member_command, DocumentRegionErrorCode.REGION_COUNT_INVALID),
    SemanticCase(
        lambda: replace(
            _two_existing_command(),
            members=(replace(_two_existing_command().members[0], order_index=2),),
        ),
        DocumentRegionErrorCode.REGION_ORDER_INVALID,
    ),
    SemanticCase(
        lambda: replace(
            _valid_command(), region_set_audit_event_id=_valid_command().region_set_version_id
        ),
        DocumentRegionErrorCode.IDENTITY_CONFLICT,
    ),
    SemanticCase(_invalid_selection_command, DocumentRegionErrorCode.REGION_SELECTION_INVALID),
    SemanticCase(_root_identity_invalid, DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT),
    SemanticCase(_later_identity_invalid, DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT),
    SemanticCase(
        lambda: replace(
            _valid_command(),
            members=(replace(_valid_member(), region_id=_valid_command().region_set_version_id),),
        ),
        DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT,
    ),
    SemanticCase(
        lambda: replace(
            _two_existing_command(),
            members=(
                _two_existing_command().members[0],
                replace(
                    _two_existing_command().members[1],
                    region_id=_two_existing_command().members[0].region_id,
                ),
            ),
        ),
        DocumentRegionErrorCode.DUPLICATE_REGION,
    ),
    SemanticCase(_duplicate_existing_selection, DocumentRegionErrorCode.DUPLICATE_REGION),
    SemanticCase(_duplicate_new_quadrilateral, DocumentRegionErrorCode.DUPLICATE_REGION),
)


@pytest.mark.parametrize("case", SEMANTIC_CASES, ids=lambda case: case.code.value)
def test_source_independent_semantics_fail_before_any_dependency(case: SemanticCase) -> None:
    value = case.build()
    factory = Factory(valid_geometry_recipe())
    read, write = tuple(factory.units)
    media: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        service.confirm_document_regions(
            value,
            storage=Storage(media),
            decoder=Decoder(media),
            renderer=Renderer(media),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is case.code
    assert factory.calls == 0
    assert media == []
    assert read.enters == read.exits == write.enters == write.exits == 0
    assert read.commits == read.rollbacks == write.commits == write.rollbacks == 0
    assert all(repo.add_calls == [] for unit in (read, write) for repo in unit._repositories())
    assert str(value.region_set_version_id) not in str(caught.value)
    assert str(value.region_set_version_id) not in repr(caught.value)


def _local_alias_command(target: str) -> ConfirmDocumentRegionsCommand:
    value = _two_new_command()
    first, second = value.members
    first_selection = first.recipe_selection
    second_selection = second.recipe_selection
    assert isinstance(first_selection, NewRecipeRevision)
    assert isinstance(second_selection, NewRecipeRevision)
    aliases = {
        "set": value.region_set_version_id,
        "set-audit": value.region_set_audit_event_id,
        "unrelated-recipe": second_selection.recipe_version_id,
        "recipe-audit": first_selection.recipe_audit_event_id,
        "other-member-recipe": first_selection.recipe_version_id,
    }
    member = first if target != "other-member-recipe" else second
    changed = replace(member, region_id=aliases[target])
    return replace(value, members=(changed, second) if member is first else (first, changed))


@pytest.mark.parametrize(
    "target",
    ("set", "set-audit", "unrelated-recipe", "recipe-audit", "other-member-recipe"),
)
def test_command_local_region_aliases_are_rejected_before_uow(target: str) -> None:
    value = _local_alias_command(target)
    factory = Factory()
    with pytest.raises(DocumentRegionsError) as caught:
        run(value, factory)
    assert caught.value.code is DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT
    assert factory.calls == 0


def test_new_root_own_recipe_alias_is_allowed_and_deduplicated() -> None:
    template = valid_geometry_recipe()
    recipe_id = entity_id(31)
    value = replace(
        command(template),
        members=(
            RegionSetMemberInput(
                1,
                recipe_id,
                new_selection(recipe_id, entity_id(41), template.quadrilateral),
            ),
        ),
    )
    factory = Factory()
    write = factory.units[1]
    result, _media = run(value, factory)
    candidates = [
        value.region_set_version_id,
        value.region_set_audit_event_id,
        recipe_id,
        value.members[0].recipe_selection.recipe_audit_event_id,
    ]
    assert result.selected_recipes[0].region_id == recipe_id
    assert write.document_region_sets.get_calls == candidates
    assert write.image_geometry_recipes.get_calls == candidates
    assert write.audit_events.get_calls == candidates


def _record_for(namespace: str, key):
    attribute = {
        "document_region_sets": "region_set_version_id",
        "image_geometry_recipes": "recipe_version_id",
        "audit_events": "event_id",
    }[namespace]
    return SimpleNamespace(**{attribute: key})


CROSS_REPOSITORY_CASES = (
    ("region-set", "image_geometry_recipes"),
    ("region-set", "audit_events"),
    ("set-audit", "document_region_sets"),
    ("set-audit", "image_geometry_recipes"),
    ("recipe", "document_region_sets"),
    ("recipe", "audit_events"),
    ("recipe-audit", "document_region_sets"),
    ("recipe-audit", "image_geometry_recipes"),
)


@pytest.mark.parametrize(("category", "namespace"), CROSS_REPOSITORY_CASES)
def test_cross_repository_created_id_collision_is_private_and_atomic(
    category: str, namespace: str
) -> None:
    value = _two_new_command()
    selection = value.members[0].recipe_selection
    assert isinstance(selection, NewRecipeRevision)
    key = {
        "region-set": value.region_set_version_id,
        "set-audit": value.region_set_audit_event_id,
        "recipe": selection.recipe_version_id,
        "recipe-audit": selection.recipe_audit_event_id,
    }[category]
    factory = Factory()
    read, write = tuple(factory.units)
    setattr(write, namespace, Repo((_record_for(namespace, key),)))
    committed = tuple(dict(repo.committed) for repo in write._repositories())
    media: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        service.confirm_document_regions(
            value,
            storage=Storage(media),
            decoder=Decoder(media),
            renderer=Renderer(media),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.IDENTITY_CONFLICT
    assert factory.calls == 2
    assert read.enters == read.exits == write.enters == write.exits == 1
    assert media == ["storage.read", "decode", "render", "render"]
    assert all(repo.add_calls == [] for repo in write._repositories())
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repo.pending == {} for repo in write._repositories())
    assert tuple(repo.committed for repo in write._repositories()) == committed
    assert str(key) not in str(caught.value) and str(key) not in repr(caught.value)


@pytest.mark.parametrize("namespace", ("document_region_sets", "audit_events"))
def test_persisted_region_id_set_or_audit_collision_is_private_and_atomic(namespace: str) -> None:
    root = valid_geometry_recipe()
    value = command(root)
    factory = Factory(root)
    read, write = tuple(factory.units)
    setattr(write, namespace, Repo((_record_for(namespace, root.region_id),)))
    committed = tuple(dict(repo.committed) for repo in write._repositories())
    media: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        service.confirm_document_regions(
            value,
            storage=Storage(media),
            decoder=Decoder(media),
            renderer=Renderer(media),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT
    assert factory.calls == 2
    assert read.enters == read.exits == write.enters == write.exits == 1
    assert media == ["storage.read", "decode", "render"]
    assert all(repo.add_calls == [] for repo in write._repositories())
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repo.pending == {} for repo in write._repositories())
    assert tuple(repo.committed for repo in write._repositories()) == committed
    assert str(root.region_id) not in str(caught.value) and str(root.region_id) not in repr(
        caught.value
    )


def test_persisted_region_id_unrelated_recipe_collision_is_rejected() -> None:
    root = valid_geometry_recipe()
    later = replace(
        root,
        recipe_version_id=entity_id(31),
        superseded_recipe_version_id=root.recipe_version_id,
        revision=2,
    )
    value = replace(
        command(later),
        members=(
            RegionSetMemberInput(
                1, root.region_id, ExistingRecipeSelection(later.recipe_version_id)
            ),
        ),
    )
    unrelated = replace(root, source_file_id=entity_id(99))
    factory = Factory(root, later)
    read, write = tuple(factory.units)
    write.image_geometry_recipes = Repo((unrelated, later))
    committed = tuple(dict(repo.committed) for repo in write._repositories())
    media: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        service.confirm_document_regions(
            value,
            storage=Storage(media),
            decoder=Decoder(media),
            renderer=Renderer(media),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.REGION_IDENTITY_CONFLICT
    assert factory.calls == 2
    assert read.enters == read.exits == write.enters == write.exits == 1
    assert media == ["storage.read", "decode", "render"]
    assert all(repo.add_calls == [] for repo in write._repositories())
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repo.pending == {} for repo in write._repositories())
    assert tuple(repo.committed for repo in write._repositories()) == committed
    assert str(root.region_id) not in str(caught.value) and str(root.region_id) not in repr(
        caught.value
    )


def test_same_source_existing_root_recipe_identity_is_allowed() -> None:
    root = valid_geometry_recipe()
    result, media = run(command(root), Factory(root))
    assert result.selected_recipes == (root,)
    assert media == ["storage.read", "decode", "render"]


def test_later_revision_retaining_same_lineage_root_is_allowed() -> None:
    root = valid_geometry_recipe()
    previous, _ = run(command(root), Factory(root))
    value = replace(
        command(root),
        region_set_version_id=entity_id(62),
        region_set_audit_event_id=entity_id(63),
        superseded_region_set_version_id=previous.region_set.region_set_version_id,
        set_revision=2,
        members=(
            RegionSetMemberInput(
                1,
                root.region_id,
                new_selection(
                    entity_id(31),
                    entity_id(41),
                    root.quadrilateral,
                    revision=2,
                    predecessor=root.recipe_version_id,
                ),
            ),
        ),
    )
    result, _ = run(value, with_previous(Factory(root), previous.region_set))
    assert result.selected_recipes[0].region_id == root.region_id
    assert result.selected_recipes[0].revision == 2


def test_stale_state_precedes_cross_repository_identity_collision() -> None:
    root = valid_geometry_recipe()
    value = command(root)
    factory = Factory(root)
    _read, write = tuple(factory.units)
    write.source_files = Repo((replace(valid_source_file(), width=31),))
    write.audit_events = Repo((_record_for("audit_events", value.region_set_version_id),))
    media: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        service.confirm_document_regions(
            value,
            storage=Storage(media),
            decoder=Decoder(media),
            renderer=Renderer(media),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.PERSISTED_DATA_INVALID
    assert value.region_set_version_id not in write.document_region_sets.get_calls
    assert value.region_set_version_id not in write.image_geometry_recipes.get_calls
    assert value.region_set_version_id not in write.audit_events.get_calls
    assert media == ["storage.read", "decode", "render"]
    assert write.commits == 0 and write.rollbacks == 1


def test_cross_repository_identity_collision_precedes_set_revision_conflict(monkeypatch) -> None:
    root = valid_geometry_recipe()
    previous, _ = run(command(root), Factory(root))
    value = replace(
        command(root),
        region_set_version_id=entity_id(62),
        region_set_audit_event_id=entity_id(63),
    )
    factory = Factory(root)
    read, write = tuple(factory.units)
    read.document_region_sets = Repo((previous.region_set,))
    write.document_region_sets = Repo((previous.region_set,))
    collision = _record_for("image_geometry_recipes", value.region_set_version_id)
    write.image_geometry_recipes = Repo((root, collision))
    revision_checks = 0
    original = service._verify_set_revision

    def verify_revision(*args, **kwargs):
        nonlocal revision_checks
        revision_checks += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_verify_set_revision", verify_revision)
    media: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        service.confirm_document_regions(
            value,
            storage=Storage(media),
            decoder=Decoder(media),
            renderer=Renderer(media),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.IDENTITY_CONFLICT
    assert revision_checks == 0
    assert value.region_set_version_id in write.image_geometry_recipes.get_calls
    assert media == ["storage.read", "decode", "render"]
    assert write.commits == 0 and write.rollbacks == 1
