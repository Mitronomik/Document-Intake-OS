from dataclasses import replace

import pytest
from tests.support.pr011 import (
    STAMP,
    actor,
    entity_id,
    valid_geometry_recipe,
    valid_original_stored_artifact,
    valid_source_file,
)

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
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


class Repo:
    def __init__(self, items=()):
        self.items = {
            getattr(x, "recipe_version_id", getattr(x, "id", getattr(x, "artifact_id", None))): x
            for x in items
        }

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
        self.items[
            getattr(
                item,
                "region_set_version_id",
                getattr(item, "recipe_version_id", getattr(item, "event_id", None)),
            )
        ] = item


class Uow:
    def __init__(self, recipe):
        self.source_files = Repo((valid_source_file(),))
        self.stored_artifacts = Repo((valid_original_stored_artifact(),))
        self.image_geometry_recipes = Repo((recipe,))
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
    def __init__(self, recipe):
        self.units = [Uow(recipe), Uow(recipe)]

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
