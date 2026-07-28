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
from document_intake.domain.enums import SourceMediaType
from document_intake.domain.image_geometry import derive_geometry_dimensions
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
        self.items = {self._key(item): item for item in items}

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
        return self.items.get(key)

    def get_latest_by_region(self, source, region):
        scoped = [
            item
            for item in self.items.values()
            if getattr(item, "source_file_id", None) == source
            and getattr(item, "region_id", None) == region
        ]
        return max(scoped, key=lambda item: item.revision) if scoped else None

    def list_by_source(self, source):
        return tuple(
            item for item in self.items.values() if getattr(item, "source_file_id", None) == source
        )

    def get_latest_by_source(self, source):
        scoped = self.list_by_source(source)
        return max(scoped, key=lambda item: item.revision) if scoped else None

    def add(self, item):
        self.items[self._key(item)] = item


class Uow:
    def __init__(self, recipes=()):
        self.source_files = Repo((valid_source_file(),))
        self.stored_artifacts = Repo((valid_original_stored_artifact(),))
        self.image_geometry_recipes = Repo(recipes)
        self.document_region_sets = Repo()
        self.audit_events = Repo()
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        self.commits += 1


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
    assert len(write.document_region_sets.items) == 1
    assert len(write.audit_events.items) == 2
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
    assert len(write.document_region_sets.items) == 1
    assert len(write.audit_events.items) == 3
    assert read.commits == 0 and write.commits == 1
    assert calls.count("render") == 2


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
    assert len(write.audit_events.items) == 1
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

    def broken():
        raise RuntimeError("private")

    factory.units[1].commit = broken
    with pytest.raises(DocumentRegionsError) as error:
        run(command(recipe), factory)
    assert error.value.code is DocumentRegionErrorCode.COMMIT_FAILED


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
