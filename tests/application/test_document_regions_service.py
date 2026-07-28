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
from document_intake.application.services.document_regions import (
    DocumentRegionsError,
    confirm_document_regions,
)
from document_intake.domain.document_regions import DocumentRegionErrorCode


class Repo:
    def __init__(self, items=()):
        self.items = {
            getattr(x, "recipe_version_id", getattr(x, "id", getattr(x, "artifact_id", None))): x
            for x in items
        }

    def get(self, key):
        return self.items.get(key)

    def get_latest_by_region(self, source, region):
        return next(iter(self.items.values()), None)

    def get_latest_by_source(self, source):
        return None

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
