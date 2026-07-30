from dataclasses import dataclass, replace

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ConfirmDocumentRegionsResult,
    ExistingRecipeSelection,
    NewRecipeRevision,
    RegionSetMemberInput,
)
from document_intake.application.ports.media import DecodedGeometryMedia, RenderedGeometryRaster
from document_intake.application.services.document_regions import (
    confirm_document_regions,
)
from document_intake.domain.document_regions import DocumentRegionSetVersion
from document_intake.domain.enums import SourceMediaType
from document_intake.domain.image_geometry import (
    GeometryPoint,
    ImageGeometryRecipe,
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


@dataclass(frozen=True, slots=True)
class RegionTransitionState:
    recipes: tuple[ImageGeometryRecipe, ...]
    region_sets: tuple[DocumentRegionSetVersion, ...]
    writes: tuple[Uow, ...] = ()
    snapshots: tuple[tuple[object, ...], ...] = ()
    results: tuple[ConfirmDocumentRegionsResult, ...] = ()


def _changed_a_quadrilateral() -> SourceQuadrilateral:
    return SourceQuadrilateral(
        GeometryPoint(1, 0), GeometryPoint(32, 0), GeometryPoint(32, 24), GeometryPoint(1, 24)
    )


def _c1_quadrilateral() -> SourceQuadrilateral:
    return SourceQuadrilateral(
        GeometryPoint(12, 0), GeometryPoint(32, 0), GeometryPoint(32, 24), GeometryPoint(12, 24)
    )


def _changed_c_quadrilateral() -> SourceQuadrilateral:
    return SourceQuadrilateral(
        GeometryPoint(10, 0), GeometryPoint(30, 0), GeometryPoint(30, 24), GeometryPoint(10, 24)
    )


def _run_transition(value, state):
    factory = Factory(*state.recipes)
    for unit in factory.units:
        unit.document_region_sets = Repo(state.region_sets)
    write = factory.units[1]
    result, _ = run(value, factory)
    return result, write


def _region_set_value_snapshot(region_set):
    return (
        region_set.region_set_version_id,
        region_set.source_file_id,
        region_set.superseded_region_set_version_id,
        region_set.revision,
        region_set.confirmed_at,
        region_set.confirmed_by,
        tuple(
            (m.order_index, m.region_id, m.geometry_recipe_version_id) for m in region_set.members
        ),
    )


def _recipe_value_snapshot(recipe):
    return (
        recipe.recipe_version_id,
        recipe.source_file_id,
        recipe.superseded_recipe_version_id,
        recipe.revision,
        recipe.coordinate_space,
        recipe.source_effective_width,
        recipe.source_effective_height,
        recipe.quarter_turn,
        recipe.quadrilateral,
        recipe.pipeline,
        recipe.created_at,
        recipe.region_id,
    )


def _advance(state, result, write, *new_recipes):
    return RegionTransitionState(
        (*state.recipes, *new_recipes),
        (*state.region_sets, result.region_set),
        (*state.writes, write),
        (*state.snapshots, _region_set_value_snapshot(result.region_set)),
        (*state.results, result),
    )


def _build_synthetic_post_migration_a_lineage() -> RegionTransitionState:
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
    return RegionTransitionState((a1, a2, a3), ())


def _confirm_first_existing_a3(state):
    a3 = state.recipes[2]
    value = replace(
        command(a3),
        members=(
            RegionSetMemberInput(1, a3.region_id, ExistingRecipeSelection(a3.recipe_version_id)),
        ),
    )
    result, write = _run_transition(value, state)
    return _advance(state, result, write)


def _expand_one_to_two(state):
    a3 = state.recipes[2]
    c1_id = entity_id(33)
    value = ConfirmDocumentRegionsCommand(
        entity_id(62),
        a3.source_file_id,
        state.region_sets[-1].region_set_version_id,
        2,
        (
            RegionSetMemberInput(1, a3.region_id, ExistingRecipeSelection(a3.recipe_version_id)),
            RegionSetMemberInput(
                2, c1_id, new_selection(c1_id, entity_id(42), _c1_quadrilateral())
            ),
        ),
        entity_id(72),
        STAMP,
        actor(),
        None,
    )
    result, write = _run_transition(value, state)
    return _advance(state, result, write, result.selected_recipes[1])


def _revise_a_only(state):
    a3, c1 = state.recipes[2], state.recipes[3]
    a4_id = entity_id(34)
    value = ConfirmDocumentRegionsCommand(
        entity_id(63),
        a3.source_file_id,
        state.region_sets[-1].region_set_version_id,
        3,
        (
            RegionSetMemberInput(
                1,
                a3.region_id,
                new_selection(
                    a4_id,
                    entity_id(43),
                    _changed_a_quadrilateral(),
                    revision=4,
                    predecessor=a3.recipe_version_id,
                ),
            ),
            RegionSetMemberInput(2, c1.region_id, ExistingRecipeSelection(c1.recipe_version_id)),
        ),
        entity_id(73),
        STAMP,
        actor(),
        None,
    )
    result, write = _run_transition(value, state)
    return _advance(state, result, write, result.selected_recipes[0])


def _revise_c_only(state):
    a4, c1 = state.recipes[4], state.recipes[3]
    c2_id = entity_id(35)
    value = ConfirmDocumentRegionsCommand(
        entity_id(64),
        a4.source_file_id,
        state.region_sets[-1].region_set_version_id,
        4,
        (
            RegionSetMemberInput(1, a4.region_id, ExistingRecipeSelection(a4.recipe_version_id)),
            RegionSetMemberInput(
                2,
                c1.region_id,
                new_selection(
                    c2_id,
                    entity_id(44),
                    _changed_c_quadrilateral(),
                    revision=2,
                    predecessor=c1.recipe_version_id,
                ),
            ),
        ),
        entity_id(74),
        STAMP,
        actor(),
        None,
    )
    result, write = _run_transition(value, state)
    return _advance(state, result, write, result.selected_recipes[1])


def _change_order_only(state):
    a4, c2 = state.recipes[4], state.recipes[5]
    value = ConfirmDocumentRegionsCommand(
        entity_id(65),
        a4.source_file_id,
        state.region_sets[-1].region_set_version_id,
        5,
        (
            RegionSetMemberInput(1, c2.region_id, ExistingRecipeSelection(c2.recipe_version_id)),
            RegionSetMemberInput(2, a4.region_id, ExistingRecipeSelection(a4.recipe_version_id)),
        ),
        entity_id(75),
        STAMP,
        actor(),
        None,
    )
    result, write = _run_transition(value, state)
    return _advance(state, result, write)


def _reduce_two_to_one(state):
    c2 = state.recipes[5]
    value = ConfirmDocumentRegionsCommand(
        entity_id(66),
        c2.source_file_id,
        state.region_sets[-1].region_set_version_id,
        6,
        (RegionSetMemberInput(1, c2.region_id, ExistingRecipeSelection(c2.recipe_version_id)),),
        entity_id(76),
        STAMP,
        actor(),
        None,
    )
    result, write = _run_transition(value, state)
    return _advance(state, result, write)


def _revise_both_command(history):
    a3, c1 = history.recipes[2], history.recipes[3]
    a4_id, c2_id = entity_id(36), entity_id(37)
    return ConfirmDocumentRegionsCommand(
        entity_id(67),
        a3.source_file_id,
        history.region_sets[1].region_set_version_id,
        3,
        (
            RegionSetMemberInput(
                1,
                a3.region_id,
                new_selection(
                    a4_id,
                    entity_id(45),
                    _changed_a_quadrilateral(),
                    revision=4,
                    predecessor=a3.recipe_version_id,
                ),
            ),
            RegionSetMemberInput(
                2,
                c1.region_id,
                new_selection(
                    c2_id,
                    entity_id(46),
                    _changed_c_quadrilateral(),
                    revision=2,
                    predecessor=c1.recipe_version_id,
                ),
            ),
        ),
        entity_id(77),
        STAMP,
        actor(),
        None,
    )


def _revise_both_factory(history):
    factory = Factory(*history.recipes[:4])
    for unit in factory.units:
        unit.document_region_sets = Repo(history.region_sets[:2])
    return factory
