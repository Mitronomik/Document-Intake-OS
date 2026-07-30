from dataclasses import replace
from types import SimpleNamespace

import pytest

import document_intake.application.services.document_regions as regions_service
from document_intake.application.dto.document_regions import (
    ExistingRecipeSelection,
    RegionSetMemberInput,
)
from document_intake.application.services.document_regions import (
    DocumentRegionsError,
    confirm_document_regions,
)
from document_intake.application.services.image_geometry import ImageGeometryError
from document_intake.domain.document_regions import DocumentRegionErrorCode
from document_intake.domain.enums import AuditAction, AuditSubjectType
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryErrorCode,
    GeometryPoint,
    SourceQuadrilateral,
    derive_geometry_dimensions,
)
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import (
    entity_id,
    valid_geometry_recipe,
    valid_source_file,
)
from tests.support.pr012_application import (
    Decoder,
    Factory,
    Renderer,
    Repo,
    Storage,
    _build_synthetic_post_migration_a_lineage,
    _c1_quadrilateral,
    _change_order_only,
    _confirm_first_existing_a3,
    _expand_one_to_two,
    _recipe_value_snapshot,
    _reduce_two_to_one,
    _region_set_value_snapshot,
    _revise_a_only,
    _revise_both_command,
    _revise_both_factory,
    _revise_c_only,
    _run_transition,
    command,
    new_selection,
    run,
    with_previous,
)


def test_invalid_count_fails_before_dependencies() -> None:
    recipe = valid_geometry_recipe()
    bad = replace(command(recipe), members=())
    with pytest.raises(DocumentRegionsError) as error:
        confirm_document_regions(
            bad,
            decoder=object(),
            renderer=object(),
            storage=object(),
            unit_of_work_factory=object(),
        )
    assert error.value.code is DocumentRegionErrorCode.REGION_COUNT_INVALID


def test_duplicate_existing_quadrilaterals_are_rejected_after_resolution() -> None:
    recipe = valid_geometry_recipe()
    second = replace(recipe, recipe_version_id=entity_id(31), region_id=entity_id(31))
    cmd = replace(
        command(recipe),
        members=(
            RegionSetMemberInput(
                1, recipe.region_id, ExistingRecipeSelection(recipe.recipe_version_id)
            ),
            RegionSetMemberInput(
                2, second.region_id, ExistingRecipeSelection(second.recipe_version_id)
            ),
        ),
    )
    factory = Factory(recipe)
    factory.units[0].image_geometry_recipes = Repo((recipe, second))
    with pytest.raises(DocumentRegionsError) as error:
        confirm_document_regions(
            cmd, decoder=object(), renderer=object(), storage=object(), unit_of_work_factory=factory
        )
    assert error.value.code is DocumentRegionErrorCode.DUPLICATE_REGION


def test_successful_one_existing_recipe_decodes_and_renders_once() -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)
    read, write = tuple(factory.units)
    result, calls = run(command(recipe), factory)
    assert result.selected_recipes == (recipe,)
    assert calls == ["storage.read", "decode", "render"]
    assert read.commits == 0 and write.commits == 1
    assert len(write.image_geometry_recipes.items) == 1
    assert len(write.audit_events.items) == 1


def test_one_entirely_new_region_creates_root_recipe_and_atomic_set() -> None:
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
    read, write = tuple(factory.units)
    result, calls = run(value, factory)
    recipe = result.selected_recipes[0]
    assert recipe.revision == 1
    assert recipe.region_id == recipe.recipe_version_id == recipe_id
    assert recipe.superseded_recipe_version_id is None
    assert result.region_set.revision == 1
    assert tuple(member.order_index for member in result.region_set.members) == (1,)
    assert calls == ["storage.read", "decode", "render"]
    assert len(write.image_geometry_recipes.items) == 1
    assert write.image_geometry_recipes.add_calls == [recipe]
    assert len(write.document_region_sets.items) == 1
    assert write.document_region_sets.add_calls == [result.region_set]
    assert [event.action_code for event in write.audit_events.add_calls] == [
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
    ]
    assert [event.subject_id for event in write.audit_events.add_calls] == [
        recipe_id,
        value.region_set_version_id,
    ]
    assert read.commits == 0 and write.commits == 1


def test_two_entirely_new_regions_create_independent_ordered_lineages() -> None:
    template = valid_geometry_recipe()
    second_quad = replace(
        template.quadrilateral,
        top_left=replace(template.quadrilateral.top_left, x=1),
    )
    first_id, second_id = entity_id(31), entity_id(32)
    value = replace(
        command(template),
        members=(
            RegionSetMemberInput(
                1,
                first_id,
                new_selection(first_id, entity_id(41), template.quadrilateral),
            ),
            RegionSetMemberInput(
                2,
                second_id,
                new_selection(second_id, entity_id(42), second_quad),
            ),
        ),
    )
    factory = Factory()
    read, write = tuple(factory.units)
    result, calls = run(value, factory)
    first, second = result.selected_recipes
    assert (first.revision, second.revision) == (1, 1)
    assert first.region_id == first.recipe_version_id == first_id
    assert second.region_id == second.recipe_version_id == second_id
    assert first.region_id != second.region_id
    assert tuple(member.region_id for member in result.region_set.members) == (
        first_id,
        second_id,
    )
    assert len(write.image_geometry_recipes.items) == 2
    assert write.image_geometry_recipes.add_calls == [first, second]
    assert len(write.document_region_sets.items) == 1
    assert [event.action_code for event in write.audit_events.add_calls] == [
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
    ]
    assert [event.subject_type for event in write.audit_events.add_calls] == [
        AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
        AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
        AuditSubjectType.DOCUMENT_REGION_SET,
    ]
    assert read.commits == 0 and write.commits == 1
    assert calls.count("render") == 2


@pytest.mark.parametrize(
    ("first_quad", "second_quad"),
    [
        pytest.param(
            SourceQuadrilateral(
                GeometryPoint(0, 0),
                GeometryPoint(16, 0),
                GeometryPoint(16, 24),
                GeometryPoint(0, 24),
            ),
            SourceQuadrilateral(
                GeometryPoint(16, 0),
                GeometryPoint(32, 0),
                GeometryPoint(32, 24),
                GeometryPoint(16, 24),
            ),
            id="touching",
        ),
        pytest.param(
            SourceQuadrilateral(
                GeometryPoint(0, 0),
                GeometryPoint(20, 0),
                GeometryPoint(20, 24),
                GeometryPoint(0, 24),
            ),
            SourceQuadrilateral(
                GeometryPoint(12, 0),
                GeometryPoint(32, 0),
                GeometryPoint(32, 24),
                GeometryPoint(12, 24),
            ),
            id="partial-overlap",
        ),
    ],
)
def test_distinct_touching_and_partially_overlapping_regions_are_accepted(
    first_quad, second_quad
) -> None:
    template = valid_geometry_recipe()
    first_id, second_id = entity_id(31), entity_id(32)
    value = replace(
        command(template),
        members=(
            RegionSetMemberInput(1, first_id, new_selection(first_id, entity_id(41), first_quad)),
            RegionSetMemberInput(
                2, second_id, new_selection(second_id, entity_id(42), second_quad)
            ),
        ),
    )
    factory = Factory()
    result, calls = run(value, factory)

    assert tuple(recipe.region_id for recipe in result.selected_recipes) == (
        first_id,
        second_id,
    )
    assert result.selected_recipes[0].quadrilateral == first_quad
    assert result.selected_recipes[1].quadrilateral == second_quad
    assert calls == ["storage.read", "decode", "render", "render"]


def test_existing_plus_new_inserts_only_new_recipe_in_command_order() -> None:
    existing = valid_geometry_recipe()
    new_id = entity_id(31)
    new_quad = replace(
        existing.quadrilateral,
        top_left=replace(existing.quadrilateral.top_left, x=1),
    )
    value = replace(
        command(existing),
        members=(
            RegionSetMemberInput(
                1,
                existing.region_id,
                ExistingRecipeSelection(existing.recipe_version_id),
            ),
            RegionSetMemberInput(
                2,
                new_id,
                new_selection(new_id, entity_id(41), new_quad),
            ),
        ),
    )
    factory = Factory(existing)
    _, write = tuple(factory.units)
    result, _ = run(value, factory)
    assert result.selected_recipes[0] is existing
    assert result.selected_recipes[1].region_id == new_id
    assert write.image_geometry_recipes.add_calls == [result.selected_recipes[1]]
    assert tuple(write.image_geometry_recipes.items.values()) == (
        existing,
        result.selected_recipes[1],
    )
    assert len(write.document_region_sets.items) == 1


def test_revision_preserves_lineage_and_exact_predecessor() -> None:
    root = valid_geometry_recipe()
    first_factory = Factory(root)
    previous, _ = run(command(root), first_factory)
    revision_id = entity_id(31)
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
                    revision_id,
                    entity_id(41),
                    root.quadrilateral,
                    revision=2,
                    predecessor=root.recipe_version_id,
                ),
            ),
        ),
    )
    factory = with_previous(Factory(root), previous.region_set)
    _, write = tuple(factory.units)
    result, _ = run(value, factory)
    revised = result.selected_recipes[0]
    assert revised.revision == 2
    assert revised.region_id == root.region_id
    assert revised.superseded_recipe_version_id == root.recipe_version_id
    assert write.image_geometry_recipes.add_calls == [revised]
    assert write.image_geometry_recipes.get(root.recipe_version_id) == root
    assert result.region_set.members[0].geometry_recipe_version_id == revision_id
    assert write.document_region_sets.get(previous.region_set.region_set_version_id) is not None


def test_order_only_revision_reverses_members_without_geometry_or_recipe_audits() -> None:
    first = valid_geometry_recipe()
    second_id = entity_id(31)
    second = replace(
        first,
        recipe_version_id=second_id,
        region_id=second_id,
        quadrilateral=replace(
            first.quadrilateral,
            top_left=replace(first.quadrilateral.top_left, x=1),
        ),
    )
    initial = replace(
        command(first),
        members=(
            RegionSetMemberInput(
                1, first.region_id, ExistingRecipeSelection(first.recipe_version_id)
            ),
            RegionSetMemberInput(
                2, second.region_id, ExistingRecipeSelection(second.recipe_version_id)
            ),
        ),
    )
    previous, _ = run(initial, Factory(first, second))
    reordered = replace(
        initial,
        region_set_version_id=entity_id(62),
        region_set_audit_event_id=entity_id(63),
        superseded_region_set_version_id=previous.region_set.region_set_version_id,
        set_revision=2,
        members=(
            replace(initial.members[1], order_index=1),
            replace(initial.members[0], order_index=2),
        ),
    )
    factory = with_previous(Factory(first, second), previous.region_set)
    _, write = tuple(factory.units)
    result, _ = run(reordered, factory)
    assert result.selected_recipes == (second, first)
    assert tuple(member.region_id for member in result.region_set.members) == (
        second.region_id,
        first.region_id,
    )
    assert len(write.image_geometry_recipes.items) == 2
    assert write.image_geometry_recipes.add_calls == []
    assert [event.action_code for event in write.audit_events.add_calls] == [
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED
    ]
    assert write.audit_events.add_calls[0].subject_id == reordered.region_set_version_id
    assert write.document_region_sets.get(previous.region_set.region_set_version_id) is not None


def test_successful_two_existing_recipes_render_each_once() -> None:
    first = valid_geometry_recipe()
    second_id = entity_id(31)
    second = replace(
        first,
        recipe_version_id=second_id,
        region_id=second_id,
        quadrilateral=replace(
            first.quadrilateral, top_left=replace(first.quadrilateral.top_left, x=1)
        ),
    )
    value = replace(
        command(first),
        members=(
            RegionSetMemberInput(
                1, first.region_id, ExistingRecipeSelection(first.recipe_version_id)
            ),
            RegionSetMemberInput(
                2, second.region_id, ExistingRecipeSelection(second.recipe_version_id)
            ),
        ),
    )
    factory = Factory(first)
    for unit in factory.units:
        unit.image_geometry_recipes = Repo((first, second))
    result, calls = run(value, factory)
    assert result.selected_recipes == (first, second)
    assert calls.count("render") == 2


def test_factory_failure_is_controlled_and_private() -> None:
    class Broken:
        def unit_of_work(self):
            raise RuntimeError("private/path/id")

    with pytest.raises(DocumentRegionsError) as error:
        run(command(valid_geometry_recipe()), Broken())
    assert error.value.code is DocumentRegionErrorCode.PERSISTENCE_FAILED
    assert "private" not in str(error.value)


def test_initial_missing_source_preserves_source_not_found_error() -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)
    factory.units[0].source_files = Repo()
    with pytest.raises(ImageGeometryError) as error:
        run(command(recipe), factory)
    assert error.value.code is GeometryErrorCode.SOURCE_FILE_NOT_FOUND
    assert len(factory.units) == 1


def test_initial_missing_artifact_preserves_artifact_not_found_error() -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)
    factory.units[0].stored_artifacts = Repo()
    with pytest.raises(ImageGeometryError) as error:
        run(command(recipe), factory)
    assert error.value.code is GeometryErrorCode.ARTIFACT_NOT_FOUND
    assert len(factory.units) == 1


@pytest.mark.parametrize(("position", "delta"), [(1, -1), (1, 1), (2, -1), (2, 1)])
def test_malformed_renderer_rgb_length_fails_before_write(position, delta) -> None:
    first = valid_geometry_recipe()
    second = replace(
        first,
        recipe_version_id=entity_id(31),
        region_id=entity_id(31),
        quadrilateral=_c1_quadrilateral(),
    )
    value = replace(
        command(first),
        members=(
            RegionSetMemberInput(
                1, first.region_id, ExistingRecipeSelection(first.recipe_version_id)
            ),
            RegionSetMemberInput(
                2, second.region_id, ExistingRecipeSelection(second.recipe_version_id)
            ),
        ),
    )
    factory = Factory(first, second)

    class MalformedRenderer(Renderer):
        def __init__(self):
            super().__init__([])
            self.count = 0

        def render_geometry(self, *, media, quadrilateral, quarter_turn, pipeline):
            self.count += 1
            width, height = derive_geometry_dimensions(quadrilateral, quarter_turn)
            size = width * height * 3 + (delta if self.count == position else 0)
            return SimpleNamespace(
                width=width, height=height, rgb_pixels=b"\0" * size, pipeline=pipeline
            )

    renderer = MalformedRenderer()
    with pytest.raises(ImageGeometryError) as error:
        confirm_document_regions(
            value,
            decoder=Decoder([]),
            renderer=renderer,
            storage=Storage([]),
            unit_of_work_factory=factory,
        )
    assert error.value.code is GeometryErrorCode.RENDER_FAILED
    assert renderer.count == position
    assert len(factory.units) == 1


def test_commit_failure_maps_commit_failed() -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)
    write = factory.units[1]

    def broken():
        raise RuntimeError("private")

    write.commit = broken
    with pytest.raises(DocumentRegionsError) as error:
        run(command(recipe), factory)
    assert error.value.code is DocumentRegionErrorCode.COMMIT_FAILED
    assert write.commits == 0
    assert write.rollbacks == 1
    assert write.document_region_sets.pending == {}
    assert write.audit_events.pending == {}


def test_source_change_during_write_fails_closed() -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)
    factory.units[1].source_files = Repo((replace(valid_source_file(), width=31),))
    with pytest.raises(DocumentRegionsError) as error:
        run(command(recipe), factory)
    assert error.value.code is DocumentRegionErrorCode.PERSISTED_DATA_INVALID


def _revision_case():
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
    return root, previous.region_set, value


def _assert_revalidation_failure(value, factory, expected) -> None:
    write = factory.units[1]
    with pytest.raises(DocumentRegionsError) as error:
        run(value, factory)
    assert error.value.code is expected
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repository.pending == {} for repository in write._repositories())
    assert write.image_geometry_recipes.add_calls == []
    assert write.document_region_sets.add_calls == []
    assert write.audit_events.add_calls == []


def test_initial_missing_preceding_set_is_not_a_stale_write() -> None:
    root, previous, value = _revision_case()
    factory = Factory(root)
    with pytest.raises(DocumentRegionsError) as error:
        run(value, factory)
    assert error.value.code is DocumentRegionErrorCode.REGION_SET_NOT_FOUND
    assert previous.region_set_version_id not in factory.units[0].document_region_sets.items


@pytest.mark.parametrize("mutation", ["removed", "changed"])
def test_preceding_set_stale_value_fails_semantic_revalidation(mutation) -> None:
    root, previous, value = _revision_case()
    factory = with_previous(Factory(root), previous)
    replacement = (
        ()
        if mutation == "removed"
        else (
            replace(previous, confirmed_by=replace(previous.confirmed_by, actor_id=entity_id(89))),
        )
    )
    factory.units[1].document_region_sets = Repo(replacement)
    _assert_revalidation_failure(value, factory, DocumentRegionErrorCode.PERSISTED_DATA_INVALID)


def test_new_latest_set_is_a_revision_conflict() -> None:
    root, previous, value = _revision_case()
    newer = replace(
        previous,
        region_set_version_id=entity_id(64),
        superseded_region_set_version_id=previous.region_set_version_id,
        revision=2,
    )
    factory = with_previous(Factory(root), previous)
    factory.units[1].document_region_sets = Repo((previous, newer))
    _assert_revalidation_failure(
        value, factory, DocumentRegionErrorCode.REGION_SET_REVISION_CONFLICT
    )


@pytest.mark.parametrize("mutation", ["removed", "changed"])
def test_selected_existing_recipe_stale_value_precedes_id_checks(mutation) -> None:
    recipe = valid_geometry_recipe()
    value = command(recipe)
    factory = Factory(recipe)
    replacement = (
        ()
        if mutation == "removed"
        else (
            replace(
                recipe,
                quadrilateral=replace(
                    recipe.quadrilateral,
                    top_left=replace(recipe.quadrilateral.top_left, x=1),
                ),
            ),
        )
    )
    write = factory.units[1]
    write.image_geometry_recipes = Repo(replacement)
    _assert_revalidation_failure(value, factory, DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    assert value.region_set_version_id not in write.document_region_sets.get_calls


@pytest.mark.parametrize("mutation", ["removed", "changed"])
def test_exact_predecessor_stale_value_precedes_revision_checks(mutation) -> None:
    root, previous, value = _revision_case()
    factory = with_previous(Factory(root), previous)
    replacement = (
        ()
        if mutation == "removed"
        else (
            replace(
                root,
                quadrilateral=replace(
                    root.quadrilateral,
                    top_left=replace(root.quadrilateral.top_left, x=1),
                ),
            ),
        )
    )
    write = factory.units[1]
    write.image_geometry_recipes = Repo(replacement)
    _assert_revalidation_failure(value, factory, DocumentRegionErrorCode.PERSISTED_DATA_INVALID)
    assert value.region_set_version_id not in write.document_region_sets.get_calls


def test_concurrent_same_root_id_is_an_identity_conflict() -> None:
    template = valid_geometry_recipe()
    proposed_id = entity_id(31)
    value = replace(
        command(template),
        members=(
            RegionSetMemberInput(
                1,
                proposed_id,
                new_selection(proposed_id, entity_id(41), template.quadrilateral),
            ),
        ),
    )
    concurrent = replace(template, recipe_version_id=proposed_id, region_id=proposed_id)
    factory = Factory()
    repository = Repo((concurrent,))
    factory.units[1].image_geometry_recipes = repository
    assert repository.get(proposed_id) == concurrent
    assert repository.get_latest_by_region(template.source_file_id, proposed_id) == concurrent
    _assert_revalidation_failure(value, factory, DocumentRegionErrorCode.IDENTITY_CONFLICT)


def _concurrent_revision_case(*, include_revision_three):
    root, previous, value = _revision_case()
    concurrent_a2 = replace(
        root,
        recipe_version_id=entity_id(32),
        superseded_recipe_version_id=root.recipe_version_id,
        revision=2,
    )
    recipes = [root, concurrent_a2]
    if include_revision_three:
        recipes.append(
            replace(
                concurrent_a2,
                recipe_version_id=entity_id(33),
                superseded_recipe_version_id=concurrent_a2.recipe_version_id,
                revision=3,
            )
        )
    factory = with_previous(Factory(root), previous)
    repository = Repo(recipes)
    factory.units[1].image_geometry_recipes = repository
    assert repository.get(entity_id(31)) is None
    return value, factory


def test_concurrent_valid_revision_two_is_a_region_revision_conflict() -> None:
    value, factory = _concurrent_revision_case(include_revision_three=False)
    _assert_revalidation_failure(value, factory, DocumentRegionErrorCode.REGION_REVISION_CONFLICT)


def test_concurrent_valid_revision_three_chain_is_a_region_revision_conflict() -> None:
    value, factory = _concurrent_revision_case(include_revision_three=True)
    _assert_revalidation_failure(value, factory, DocumentRegionErrorCode.REGION_REVISION_CONFLICT)


@pytest.mark.parametrize(
    ("phase", "code"),
    [
        *(
            ("validate", code)
            for code in (
                GeometryErrorCode.POINT_OUT_OF_BOUNDS,
                GeometryErrorCode.DUPLICATE_POINT,
                GeometryErrorCode.NON_CLOCKWISE_QUADRILATERAL,
                GeometryErrorCode.SELF_INTERSECTING_QUADRILATERAL,
                GeometryErrorCode.NON_CONVEX_QUADRILATERAL,
                GeometryErrorCode.AREA_TOO_SMALL,
            )
        ),
        ("derive", GeometryErrorCode.OUTPUT_DIMENSIONS_TOO_SMALL),
        ("derive", GeometryErrorCode.INVALID_QUARTER_TURN),
    ],
)
def test_geometry_invalid_values_map_to_exact_controlled_code(monkeypatch, phase, code) -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)

    def fail(*_args, **_kwargs):
        raise InvalidValueError(code.value)

    target = SourceQuadrilateral if phase == "validate" else regions_service
    attribute = "validate_for_source" if phase == "validate" else "derive_geometry_dimensions"
    monkeypatch.setattr(target, attribute, fail)
    with pytest.raises(ImageGeometryError) as error:
        run(command(recipe), factory)
    assert error.value.code is code
    assert len(factory.units) == 1


@pytest.mark.parametrize(
    ("phase", "marker"),
    [
        ("validate", "private-geometry-validation-marker"),
        ("derive", "private-dimension-derivation-marker"),
    ],
)
def test_private_geometry_failures_map_to_render_failed(monkeypatch, phase, marker) -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)

    def fail(*_args, **_kwargs):
        raise RuntimeError(marker)

    target = SourceQuadrilateral if phase == "validate" else regions_service
    attribute = "validate_for_source" if phase == "validate" else "derive_geometry_dimensions"
    monkeypatch.setattr(target, attribute, fail)
    with pytest.raises(ImageGeometryError) as error:
        run(command(recipe), factory)
    assert error.value.code is GeometryErrorCode.RENDER_FAILED
    assert marker not in str(error.value) and marker not in repr(error.value)
    assert len(factory.units) == 1


def test_late_uniqueness_race_is_controlled() -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)

    def conflict(item):
        raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)

    factory.units[1].document_region_sets.add = conflict
    with pytest.raises(DocumentRegionsError) as error:
        run(command(recipe), factory)
    assert error.value.code is DocumentRegionErrorCode.PERSISTENCE_CONFLICT


def test_audit_failure_rolls_back_pending_region_set() -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)
    write = factory.units[1]

    def fail_audit(_item):
        raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)

    write.audit_events.add = fail_audit
    with pytest.raises(DocumentRegionsError) as error:
        run(command(recipe), factory)
    assert error.value.code is DocumentRegionErrorCode.PERSISTENCE_FAILED
    assert write.commits == 0
    assert write.rollbacks == 1
    assert write.document_region_sets.pending == {}
    assert write.document_region_sets.committed == {}
    assert write.audit_events.committed == {}


def test_fake_repository_rejects_duplicate_immutable_add() -> None:
    recipe = valid_geometry_recipe()
    repository = Repo((recipe,))
    with pytest.raises(PersistenceError) as error:
        repository.add(recipe)
    assert error.value.code is PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    assert repository.add_calls == [recipe]
    assert repository.committed == {recipe.recipe_version_id: recipe}
    assert repository.pending == {}


def test_fake_uow_mid_commit_failure_restores_every_repository() -> None:
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)
    write = factory.units[1]
    original_recipe_state = dict(write.image_geometry_recipes.committed)
    original_set_state = dict(write.document_region_sets.committed)
    original_audit_state = dict(write.audit_events.committed)

    def fail_commit():
        raise RuntimeError("private mid-commit failure")

    write.document_region_sets.commit = fail_commit
    with pytest.raises(DocumentRegionsError) as error:
        run(command(recipe), factory)

    assert error.value.code is DocumentRegionErrorCode.COMMIT_FAILED
    assert write.commits == 0
    assert write.rollbacks == 1
    assert write.image_geometry_recipes.committed == original_recipe_state
    assert write.document_region_sets.committed == original_set_state
    assert write.audit_events.committed == original_audit_state
    assert all(repository.pending == {} for repository in write._repositories())


def test_audit_failure_rolls_back_new_recipe_and_region_set() -> None:
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

    def fail_set_audit(item):
        if item.action_code is AuditAction.DOCUMENT_REGION_SET_CONFIRMED:
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)
        Repo.add(write.audit_events, item)

    write.audit_events.add = fail_set_audit
    with pytest.raises(DocumentRegionsError) as error:
        run(value, factory)

    assert error.value.code is DocumentRegionErrorCode.PERSISTENCE_FAILED
    assert write.commits == 0
    assert write.rollbacks == 1
    assert write.image_geometry_recipes.committed == {}
    assert write.document_region_sets.committed == {}
    assert write.audit_events.committed == {}
    assert all(repository.pending == {} for repository in write._repositories())


def _assert_audits(write, expected):
    assert [event.event_id for event in write.audit_events.add_calls] == [
        item[0] for item in expected
    ]
    assert [event.action_code for event in write.audit_events.add_calls] == [
        item[1] for item in expected
    ]
    assert [event.subject_type for event in write.audit_events.add_calls] == [
        item[2] for item in expected
    ]
    assert [event.subject_id for event in write.audit_events.add_calls] == [
        item[3] for item in expected
    ]


def test_first_set_reuses_post_migration_shaped_existing_a3() -> None:
    history = _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
    a3 = history.recipes[2]
    first, write = history.region_sets[0], history.writes[0]
    assert history.results[0].selected_recipes == (a3,)
    assert write.image_geometry_recipes.add_calls == []
    _assert_audits(
        write,
        [
            (
                entity_id(61),
                AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
                AuditSubjectType.DOCUMENT_REGION_SET,
                first.region_set_version_id,
            )
        ],
    )
    assert tuple(member.geometry_recipe_version_id for member in first.members) == (
        a3.recipe_version_id,
    )
    assert write.document_region_sets.add_calls == [first]
    assert write.commits == 1


def test_one_to_two_adds_new_independent_lineage() -> None:
    history = _expand_one_to_two(
        _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
    )
    a3, c1 = history.recipes[2], history.recipes[3]
    current, write = history.region_sets[1], history.writes[1]
    assert history.results[1].selected_recipes == (a3, c1)
    assert c1.revision == 1
    assert c1.region_id == c1.recipe_version_id
    assert c1.superseded_recipe_version_id is None
    assert write.image_geometry_recipes.add_calls == [c1]
    _assert_audits(
        write,
        [
            (
                entity_id(42),
                AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
                AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
                c1.recipe_version_id,
            ),
            (
                entity_id(72),
                AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
                AuditSubjectType.DOCUMENT_REGION_SET,
                current.region_set_version_id,
            ),
        ],
    )
    assert tuple(member.geometry_recipe_version_id for member in current.members) == (
        a3.recipe_version_id,
        c1.recipe_version_id,
    )
    assert write.commits == 1


def test_revise_one_of_two_preserves_other_exact_recipe() -> None:
    history = _revise_a_only(
        _expand_one_to_two(_confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage()))
    )
    a3, c1, a4 = history.recipes[2], history.recipes[3], history.recipes[4]
    current, write = history.region_sets[2], history.writes[2]
    assert history.results[2].selected_recipes == (a4, c1)
    assert a4.quadrilateral != a3.quadrilateral
    assert a4.region_id == a3.region_id
    assert a4.revision == a3.revision + 1
    assert a4.superseded_recipe_version_id == a3.recipe_version_id
    assert write.image_geometry_recipes.add_calls == [a4]
    _assert_audits(
        write,
        [
            (
                entity_id(43),
                AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
                AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
                a4.recipe_version_id,
            ),
            (
                entity_id(73),
                AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
                AuditSubjectType.DOCUMENT_REGION_SET,
                current.region_set_version_id,
            ),
        ],
    )
    assert tuple(member.geometry_recipe_version_id for member in current.members) == (
        a4.recipe_version_id,
        c1.recipe_version_id,
    )
    assert write.commits == 1


def test_revise_both_regions_in_one_atomic_command() -> None:
    history = _expand_one_to_two(
        _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
    )
    a3, c1 = history.recipes[2], history.recipes[3]
    a3_snapshot = _recipe_value_snapshot(a3)
    c1_snapshot = _recipe_value_snapshot(c1)
    command_value = _revise_both_command(history)
    result, write = _run_transition(command_value, history)
    a4, c2 = result.selected_recipes
    assert a4.quadrilateral != a3.quadrilateral
    assert c2.quadrilateral != c1.quadrilateral
    assert a4.quadrilateral != c2.quadrilateral
    assert (a4.region_id, c2.region_id) == (a3.region_id, c1.region_id)
    assert a4.recipe_version_id != a3.recipe_version_id
    assert a4.revision == a3.revision + 1
    assert a4.superseded_recipe_version_id == a3.recipe_version_id
    assert c2.recipe_version_id != c1.recipe_version_id
    assert c2.revision == c1.revision + 1
    assert c2.superseded_recipe_version_id == c1.recipe_version_id
    assert result.region_set.revision == history.region_sets[1].revision + 1
    assert (
        result.region_set.superseded_region_set_version_id
        == history.region_sets[1].region_set_version_id
    )
    assert write.image_geometry_recipes.add_calls == [a4, c2]
    _assert_audits(
        write,
        [
            (
                entity_id(45),
                AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
                AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
                a4.recipe_version_id,
            ),
            (
                entity_id(46),
                AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
                AuditSubjectType.IMAGE_GEOMETRY_RECIPE,
                c2.recipe_version_id,
            ),
            (
                entity_id(77),
                AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
                AuditSubjectType.DOCUMENT_REGION_SET,
                result.region_set.region_set_version_id,
            ),
        ],
    )
    assert write.document_region_sets.add_calls == [result.region_set]
    assert tuple(member.geometry_recipe_version_id for member in result.region_set.members) == (
        a4.recipe_version_id,
        c2.recipe_version_id,
    )
    assert write.commits == 1
    assert _recipe_value_snapshot(a3) == a3_snapshot
    assert _recipe_value_snapshot(c1) == c1_snapshot


def test_revise_both_global_write_order_matches_contract() -> None:
    state = _expand_one_to_two(
        _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
    )
    factory = _revise_both_factory(state)
    write = factory.units[1]
    observed = []

    def add_recipe(item):
        observed.append(f"ADD_RECIPE:{item.recipe_version_id}")
        Repo.add(write.image_geometry_recipes, item)

    def add_audit(item):
        label = (
            "ADD_SET_AUDIT"
            if item.action_code is AuditAction.DOCUMENT_REGION_SET_CONFIRMED
            else f"ADD_RECIPE_AUDIT:{item.subject_id}"
        )
        observed.append(label)
        Repo.add(write.audit_events, item)

    def add_set(item):
        observed.append("ADD_REGION_SET")
        for member in item.members:
            observed.append(
                f"ADD_MEMBERSHIP:{member.order_index}:{member.geometry_recipe_version_id}"
            )
        Repo.add(write.document_region_sets, item)

    original_commit = write.commit

    def commit():
        observed.append("COMMIT")
        original_commit()

    write.image_geometry_recipes.add = add_recipe
    write.audit_events.add = add_audit
    write.document_region_sets.add = add_set
    write.commit = commit
    result, _ = run(_revise_both_command(state), factory)
    a4, c2 = result.selected_recipes
    assert observed == [
        f"ADD_RECIPE:{a4.recipe_version_id}",
        f"ADD_RECIPE:{c2.recipe_version_id}",
        f"ADD_RECIPE_AUDIT:{a4.recipe_version_id}",
        f"ADD_RECIPE_AUDIT:{c2.recipe_version_id}",
        "ADD_REGION_SET",
        f"ADD_MEMBERSHIP:1:{a4.recipe_version_id}",
        f"ADD_MEMBERSHIP:2:{c2.recipe_version_id}",
        "ADD_SET_AUDIT",
        "COMMIT",
    ]


def test_revise_both_second_recipe_write_failure_rolls_back_all_pending_rows() -> None:
    history = _expand_one_to_two(
        _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
    )
    factory = _revise_both_factory(history)
    write = factory.units[1]
    original_recipes = dict(write.image_geometry_recipes.committed)
    original_sets = dict(write.document_region_sets.committed)
    calls = 0

    def fail_second(item):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("private-second-recipe-write-marker")
        Repo.add(write.image_geometry_recipes, item)

    write.image_geometry_recipes.add = fail_second
    with pytest.raises(DocumentRegionsError) as error:
        run(_revise_both_command(history), factory)

    assert error.value.code is DocumentRegionErrorCode.PERSISTENCE_FAILED
    assert "private-second-recipe-write-marker" not in str(error.value)
    assert "private-second-recipe-write-marker" not in repr(error.value)
    assert write.commits == 0 and write.rollbacks == 1
    assert write.image_geometry_recipes.committed == original_recipes
    assert write.document_region_sets.committed == original_sets
    assert write.audit_events.committed == {}
    assert all(repository.pending == {} for repository in write._repositories())


def test_revise_both_commit_failure_restores_all_repository_state() -> None:
    history = _expand_one_to_two(
        _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
    )
    factory = _revise_both_factory(history)
    write = factory.units[1]
    original = tuple(
        (dict(repository.committed), dict(repository.pending))
        for repository in write._repositories()
    )

    def fail_commit():
        raise RuntimeError("private commit failure")

    write.commit = fail_commit
    with pytest.raises(DocumentRegionsError) as error:
        run(_revise_both_command(history), factory)

    assert error.value.code is DocumentRegionErrorCode.COMMIT_FAILED
    assert "private commit failure" not in str(error.value)
    assert write.commits == 0 and write.rollbacks == 1
    for repository, (committed, _pending) in zip(write._repositories(), original, strict=True):
        assert repository.committed == committed
        assert repository.pending == {}


def test_order_only_revision_reuses_recipes_without_recipe_audits() -> None:
    history = _change_order_only(
        _revise_c_only(
            _revise_a_only(
                _expand_one_to_two(
                    _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
                )
            )
        )
    )
    a4, c2 = history.recipes[4], history.recipes[5]
    current, write = history.region_sets[4], history.writes[4]
    assert history.results[4].selected_recipes == (c2, a4)
    assert write.image_geometry_recipes.add_calls == []
    _assert_audits(
        write,
        [
            (
                entity_id(75),
                AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
                AuditSubjectType.DOCUMENT_REGION_SET,
                current.region_set_version_id,
            )
        ],
    )
    assert tuple(member.geometry_recipe_version_id for member in current.members) == (
        c2.recipe_version_id,
        a4.recipe_version_id,
    )
    assert write.commits == 1


def test_two_to_one_retains_selected_existing_lineage() -> None:
    history = _reduce_two_to_one(
        _change_order_only(
            _revise_c_only(
                _revise_a_only(
                    _expand_one_to_two(
                        _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
                    )
                )
            )
        )
    )
    c2 = history.recipes[5]
    current, write = history.region_sets[5], history.writes[5]
    assert history.results[5].selected_recipes == (c2,)
    assert write.image_geometry_recipes.add_calls == []
    _assert_audits(
        write,
        [
            (
                entity_id(76),
                AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
                AuditSubjectType.DOCUMENT_REGION_SET,
                current.region_set_version_id,
            )
        ],
    )
    assert tuple(member.geometry_recipe_version_id for member in current.members) == (
        c2.recipe_version_id,
    )
    assert write.commits == 1
    assert history.recipes[4] in history.writes[5].image_geometry_recipes.committed.values()


def test_transition_history_preserves_exact_value_manifest() -> None:
    history = _reduce_two_to_one(
        _change_order_only(
            _revise_c_only(
                _revise_a_only(
                    _expand_one_to_two(
                        _confirm_first_existing_a3(_build_synthetic_post_migration_a_lineage())
                    )
                )
            )
        )
    )
    a3, c1, a4, c2 = history.recipes[2:]
    expected = (
        ((a3.recipe_version_id,), (a3.region_id,)),
        ((a3.recipe_version_id, c1.recipe_version_id), (a3.region_id, c1.region_id)),
        ((a4.recipe_version_id, c1.recipe_version_id), (a4.region_id, c1.region_id)),
        ((a4.recipe_version_id, c2.recipe_version_id), (a4.region_id, c2.region_id)),
        ((c2.recipe_version_id, a4.recipe_version_id), (c2.region_id, a4.region_id)),
        ((c2.recipe_version_id,), (c2.region_id,)),
    )
    assert (
        tuple(_region_set_value_snapshot(item) for item in history.region_sets) == history.snapshots
    )
    for index, (region_set, (recipe_ids, region_ids)) in enumerate(
        zip(history.region_sets, expected, strict=True), 1
    ):
        assert region_set.revision == index
        assert region_set.source_file_id == history.recipes[0].source_file_id
        assert region_set.superseded_region_set_version_id == (
            None if index == 1 else history.region_sets[index - 2].region_set_version_id
        )
        assert tuple(member.order_index for member in region_set.members) == tuple(
            range(1, len(recipe_ids) + 1)
        )
        assert (
            tuple(member.geometry_recipe_version_id for member in region_set.members) == recipe_ids
        )
        assert tuple(member.region_id for member in region_set.members) == region_ids
