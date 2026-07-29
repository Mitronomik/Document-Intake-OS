from dataclasses import replace

import pytest

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    NewRecipeRevision,
    RegionSetMemberInput,
)
from document_intake.application.ports.media import DecodedGeometryMedia, RenderedGeometryRaster
from document_intake.application.services.document_regions import (
    DocumentRegionsError,
    confirm_document_regions,
)
from document_intake.domain.document_regions import DocumentRegionErrorCode
from document_intake.domain.enums import AuditAction, AuditSubjectType, SourceMediaType
from document_intake.domain.image_geometry import (
    GeometryPoint,
    SourceQuadrilateral,
    derive_geometry_dimensions,
)
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import (
    STAMP,
    actor,
    entity_id,
    valid_geometry_recipe,
    valid_original_stored_artifact,
    valid_source_file,
)


class Repo:
    def __init__(self, items=()):
        self.committed = {self._key(item): item for item in items}
        self.pending = {}
        self.get_calls = []
        self.get_latest_by_region_calls = []
        self.get_latest_by_source_calls = []
        self.list_by_source_calls = []
        self.add_calls = []

    @property
    def items(self):
        return self.committed | self.pending

    @staticmethod
    def _key(item):
        for attribute in (
            "region_set_version_id",
            "recipe_version_id",
            "event_id",
            "id",
            "artifact_id",
        ):
            value = getattr(item, attribute, None)
            if value is not None:
                return value
        return None

    def get(self, key):
        self.get_calls.append(key)
        return self.items.get(key)

    def get_latest_by_region(self, source, region):
        self.get_latest_by_region_calls.append((source, region))
        scoped = [
            item
            for item in self.items.values()
            if getattr(item, "source_file_id", None) == source
            and getattr(item, "region_id", None) == region
        ]
        return max(scoped, key=lambda item: item.revision) if scoped else None

    def list_by_source(self, source):
        self.list_by_source_calls.append(source)
        return tuple(
            item for item in self.items.values() if getattr(item, "source_file_id", None) == source
        )

    def get_latest_by_source(self, source):
        self.get_latest_by_source_calls.append(source)
        scoped = self.list_by_source(source)
        return max(scoped, key=lambda item: item.revision) if scoped else None

    def add(self, item):
        self.add_calls.append(item)
        key = self._key(item)
        if key in self.items:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        self.pending[key] = item

    def commit(self):
        self.committed.update(self.pending)
        self.pending.clear()

    def rollback(self):
        self.pending.clear()


class Uow:
    def __init__(self, recipes=()):
        self.source_files = Repo((valid_source_file(),))
        self.stored_artifacts = Repo((valid_original_stored_artifact(),))
        self.image_geometry_recipes = Repo(recipes)
        self.document_region_sets = Repo()
        self.audit_events = Repo()
        self.commits = 0
        self.rollbacks = 0
        self.enters = 0
        self.exits = 0

    def __enter__(self):
        self.enters += 1
        return self

    def __exit__(self, exc_type, *_args):
        self.exits += 1
        if exc_type is not None:
            self.rollback()
        return False

    def commit(self):
        repositories = self._repositories()
        snapshots = [(dict(repo.committed), dict(repo.pending)) for repo in repositories]
        try:
            for repository in repositories:
                repository.commit()
        except Exception:
            for repository, (committed, pending) in zip(repositories, snapshots, strict=True):
                repository.committed = committed
                repository.pending = pending
            raise
        self.commits += 1

    def rollback(self):
        for repository in self._repositories():
            repository.rollback()
        self.rollbacks += 1

    def _repositories(self):
        return (
            self.source_files,
            self.stored_artifacts,
            self.image_geometry_recipes,
            self.document_region_sets,
            self.audit_events,
        )


class Factory:
    def __init__(self, *recipes):
        self.units = [Uow(recipes), Uow(recipes)]

    def unit_of_work(self):
        return self.units.pop(0)


def command(recipe):
    return ConfirmDocumentRegionsCommand(
        entity_id(60),
        recipe.source_file_id,
        None,
        1,
        (
            RegionSetMemberInput(
                1, recipe.region_id, ExistingRecipeSelection(recipe.recipe_version_id)
            ),
        ),
        entity_id(61),
        STAMP,
        actor(),
        None,
    )


def new_selection(recipe_id, audit_id, quadrilateral, *, revision=1, predecessor=None):
    return NewRecipeRevision(
        recipe_id,
        predecessor,
        revision,
        quadrilateral,
        valid_geometry_recipe().quarter_turn,
        audit_id,
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


class Storage:
    def __init__(self, calls):
        self.calls = calls

    def read_bytes(self, *, expected):
        self.calls.append("storage.read")
        return b"source"

    def publish_bytes(self, **kwargs):
        raise AssertionError("storage publication")


class Decoder:
    def __init__(self, calls):
        self.calls = calls

    def decode_for_geometry(self, *, content):
        self.calls.append("decode")
        return DecodedGeometryMedia(
            SourceMediaType.JPEG, 32, 24, None, 32, 24, b"\0" * (32 * 24 * 3)
        )


class Renderer:
    def __init__(self, calls):
        self.calls = calls

    def render_geometry(self, *, media, quadrilateral, quarter_turn, pipeline):
        self.calls.append("render")
        width, height = derive_geometry_dimensions(quadrilateral, quarter_turn)
        return RenderedGeometryRaster(width, height, b"\0" * (width * height * 3), pipeline)


def run(command_value, factory):
    calls = []
    result = confirm_document_regions(
        command_value,
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        storage=Storage(calls),
        unit_of_work_factory=factory,
    )
    return result, calls


def with_previous(factory, previous):
    for unit in factory.units:
        unit.document_region_sets = Repo((previous,))
    return factory


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


def test_s1_s6_transition_flow_preserves_independent_histories() -> None:
    a1 = valid_geometry_recipe()
    a2 = replace(
        a1,
        recipe_version_id=entity_id(31),
        revision=2,
        superseded_recipe_version_id=a1.recipe_version_id,
    )
    a3 = replace(
        a2,
        recipe_version_id=entity_id(32),
        revision=3,
        superseded_recipe_version_id=a2.recipe_version_id,
    )
    recipes = [a1, a2, a3]
    sets = []

    s1_command = replace(
        command(a3),
        members=(
            RegionSetMemberInput(1, a3.region_id, ExistingRecipeSelection(a3.recipe_version_id)),
        ),
    )
    s1_factory = Factory(*recipes)
    s1_write = s1_factory.units[1]
    s1, _ = run(s1_command, s1_factory)
    sets.append(s1.region_set)
    assert s1.selected_recipes == (a3,)
    assert s1_write.image_geometry_recipes.add_calls == []
    assert [event.action_code for event in s1_write.audit_events.add_calls] == [
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED
    ]
    assert s1_write.commits == 1

    c1_id = entity_id(33)
    c_quad = SourceQuadrilateral(
        GeometryPoint(12, 0),
        GeometryPoint(32, 0),
        GeometryPoint(32, 24),
        GeometryPoint(12, 24),
    )
    s2_command = ConfirmDocumentRegionsCommand(
        entity_id(62),
        a1.source_file_id,
        s1.region_set.region_set_version_id,
        2,
        (
            RegionSetMemberInput(1, a3.region_id, ExistingRecipeSelection(a3.recipe_version_id)),
            RegionSetMemberInput(2, c1_id, new_selection(c1_id, entity_id(42), c_quad)),
        ),
        entity_id(72),
        STAMP,
        actor(),
        None,
    )
    s2_factory = with_previous(Factory(*recipes), s1.region_set)
    s2_write = s2_factory.units[1]
    s2, _ = run(s2_command, s2_factory)
    c1 = s2.selected_recipes[1]
    recipes.append(c1)
    sets.append(s2.region_set)
    assert s2.selected_recipes == (a3, c1)
    assert c1.region_id == c1.recipe_version_id == c1_id
    assert s2_write.image_geometry_recipes.add_calls == [c1]
    assert [event.action_code for event in s2_write.audit_events.add_calls] == [
        AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED,
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED,
    ]
    assert s2_write.commits == 1

    a4_id = entity_id(34)
    s3_command = replace(
        s2_command,
        region_set_version_id=entity_id(63),
        superseded_region_set_version_id=s2.region_set.region_set_version_id,
        set_revision=3,
        region_set_audit_event_id=entity_id(73),
        members=(
            RegionSetMemberInput(
                1,
                a3.region_id,
                new_selection(
                    a4_id,
                    entity_id(43),
                    a3.quadrilateral,
                    revision=4,
                    predecessor=a3.recipe_version_id,
                ),
            ),
            RegionSetMemberInput(2, c1.region_id, ExistingRecipeSelection(c1.recipe_version_id)),
        ),
    )
    s3_factory = Factory(*recipes)
    for unit in s3_factory.units:
        unit.document_region_sets = Repo(sets)
    s3_write = s3_factory.units[1]
    s3, _ = run(s3_command, s3_factory)
    a4 = s3.selected_recipes[0]
    recipes.append(a4)
    sets.append(s3.region_set)
    assert s3.selected_recipes == (a4, c1)
    assert a4.region_id == a1.region_id
    assert a4.superseded_recipe_version_id == a3.recipe_version_id
    assert s3_write.image_geometry_recipes.add_calls == [a4]
    assert s3_write.commits == 1

    c2_id = entity_id(35)
    s4_command = replace(
        s3_command,
        region_set_version_id=entity_id(64),
        superseded_region_set_version_id=s3.region_set.region_set_version_id,
        set_revision=4,
        region_set_audit_event_id=entity_id(74),
        members=(
            RegionSetMemberInput(1, a4.region_id, ExistingRecipeSelection(a4.recipe_version_id)),
            RegionSetMemberInput(
                2,
                c1.region_id,
                new_selection(
                    c2_id,
                    entity_id(44),
                    c_quad,
                    revision=2,
                    predecessor=c1.recipe_version_id,
                ),
            ),
        ),
    )
    s4_factory = Factory(*recipes)
    for unit in s4_factory.units:
        unit.document_region_sets = Repo(sets)
    s4_write = s4_factory.units[1]
    s4, _ = run(s4_command, s4_factory)
    c2 = s4.selected_recipes[1]
    recipes.append(c2)
    sets.append(s4.region_set)
    assert s4.selected_recipes == (a4, c2)
    assert c2.region_id == c1.region_id
    assert c2.superseded_recipe_version_id == c1.recipe_version_id
    assert s4_write.image_geometry_recipes.add_calls == [c2]
    assert s4_write.commits == 1

    s5_command = replace(
        s4_command,
        region_set_version_id=entity_id(65),
        superseded_region_set_version_id=s4.region_set.region_set_version_id,
        set_revision=5,
        region_set_audit_event_id=entity_id(75),
        members=(
            RegionSetMemberInput(1, c2.region_id, ExistingRecipeSelection(c2.recipe_version_id)),
            RegionSetMemberInput(2, a4.region_id, ExistingRecipeSelection(a4.recipe_version_id)),
        ),
    )
    s5_factory = Factory(*recipes)
    for unit in s5_factory.units:
        unit.document_region_sets = Repo(sets)
    s5_write = s5_factory.units[1]
    s5, _ = run(s5_command, s5_factory)
    sets.append(s5.region_set)
    assert s5.selected_recipes == (c2, a4)
    assert s5_write.image_geometry_recipes.add_calls == []
    assert [event.action_code for event in s5_write.audit_events.add_calls] == [
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED
    ]
    assert s5_write.commits == 1

    s6_command = replace(
        s5_command,
        region_set_version_id=entity_id(66),
        superseded_region_set_version_id=s5.region_set.region_set_version_id,
        set_revision=6,
        region_set_audit_event_id=entity_id(76),
        members=(
            RegionSetMemberInput(1, c2.region_id, ExistingRecipeSelection(c2.recipe_version_id)),
        ),
    )
    s6_factory = Factory(*recipes)
    for unit in s6_factory.units:
        unit.document_region_sets = Repo(sets)
    s6_write = s6_factory.units[1]
    s6, _ = run(s6_command, s6_factory)
    sets.append(s6.region_set)
    assert s6.selected_recipes == (c2,)
    assert s6_write.image_geometry_recipes.add_calls == []
    assert [event.action_code for event in s6_write.audit_events.add_calls] == [
        AuditAction.DOCUMENT_REGION_SET_CONFIRMED
    ]
    assert s6_write.commits == 1
    assert [item.revision for item in sets] == [1, 2, 3, 4, 5, 6]
    assert [item.superseded_region_set_version_id for item in sets] == [
        None,
        sets[0].region_set_version_id,
        sets[1].region_set_version_id,
        sets[2].region_set_version_id,
        sets[3].region_set_version_id,
        sets[4].region_set_version_id,
    ]
    assert [recipe.revision for recipe in recipes if recipe.region_id == a1.region_id] == [
        1,
        2,
        3,
        4,
    ]
    assert [recipe.revision for recipe in recipes if recipe.region_id == c1.region_id] == [1, 2]
