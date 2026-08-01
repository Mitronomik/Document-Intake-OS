from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from document_intake.application.dto.document_regions import (
    ExistingRecipeSelection,
    RegionSetMemberInput,
)
from document_intake.application.ports.media import DecodedGeometryMedia, RenderedGeometryRaster
from document_intake.application.services.document_region_persistence import DocumentRegionsError
from document_intake.application.services.document_regions import confirm_document_regions
from document_intake.application.services.image_geometry import ImageGeometryError
from document_intake.domain.document_regions import DocumentRegionErrorCode
from document_intake.domain.enums import SourceMediaType
from document_intake.domain.image_geometry import (
    GeometryErrorCode,
    GeometryPoint,
    SourceQuadrilateral,
)
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from tests.support.pr011 import entity_id, valid_geometry_recipe
from tests.support.pr012_application import (
    Decoder,
    Factory,
    Renderer,
    Repo,
    Storage,
    Uow,
    command,
    new_selection,
)


def _second_quadrilateral() -> SourceQuadrilateral:
    return SourceQuadrilateral(
        GeometryPoint(12, 0),
        GeometryPoint(32, 0),
        GeometryPoint(32, 24),
        GeometryPoint(12, 24),
    )


def _two_new_command():
    template = valid_geometry_recipe()
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
                new_selection(entity_id(32), entity_id(42), _second_quadrilateral()),
            ),
        ),
    )


def _two_existing_case():
    first = valid_geometry_recipe()
    second = replace(
        first,
        recipe_version_id=entity_id(32),
        region_id=entity_id(32),
        quadrilateral=_second_quadrilateral(),
    )
    value = replace(
        command(first),
        members=(
            RegionSetMemberInput(1, first.region_id, SimpleNamespace()),
            RegionSetMemberInput(2, second.region_id, SimpleNamespace()),
        ),
    )
    return (
        replace(
            value,
            members=(
                replace(
                    value.members[0],
                    recipe_selection=ExistingRecipeSelection(first.recipe_version_id),
                ),
                replace(
                    value.members[1],
                    recipe_selection=ExistingRecipeSelection(second.recipe_version_id),
                ),
            ),
        ),
        first,
        second,
    )


def _invoke(value, factory, *, storage=None, decoder=None, renderer=None):
    calls: list[str] = []
    confirm_document_regions(
        value,
        storage=storage or Storage(calls),
        decoder=decoder or Decoder(calls),
        renderer=renderer or Renderer(calls),
        unit_of_work_factory=factory,
    )


def _assert_private(error: BaseException, marker: str) -> None:
    assert marker not in str(error)
    assert marker not in repr(error)


def _assert_no_write_started(read: Uow, write: Uow) -> None:
    assert read.enters == 1
    assert write.enters == 0
    assert write.commits == 0 and write.rollbacks == 0
    assert all(repository.add_calls == [] for repository in write._repositories())


def _assert_write_rejected(write: Uow) -> None:
    assert write.enters == 1
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repository.pending == {} for repository in write._repositories())
    assert write.image_geometry_recipes.add_calls == []
    assert write.document_region_sets.add_calls == []
    assert write.audit_events.add_calls == []


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        pytest.param(
            "storage", GeometryErrorCode.ARTIFACT_INTEGRITY_FAILED, id="storage-integrity"
        ),
        pytest.param("decoder", GeometryErrorCode.DECODE_FAILED, id="decoder"),
        pytest.param("dimensions", GeometryErrorCode.SOURCE_DIMENSIONS_MISMATCH, id="dimensions"),
        pytest.param("renderer-first", GeometryErrorCode.RENDER_FAILED, id="renderer-first"),
        pytest.param("renderer-second", GeometryErrorCode.RENDER_FAILED, id="renderer-second"),
    ],
)
def test_media_failures_stop_before_write_and_remain_private(case, expected) -> None:
    marker = f"private-phase3-marker-{case}"
    value, first, second = _two_existing_case()
    factory = Factory(first, second)
    read, write = factory.units
    calls: list[str] = []

    class FaultStorage(Storage):
        published = 0

        def read_bytes(self, *, expected):
            if case == "storage":
                raise RuntimeError(marker)
            return super().read_bytes(expected=expected)

        def publish_bytes(self, **kwargs):
            self.published += 1
            raise AssertionError(marker)

    class FaultDecoder(Decoder):
        def decode_for_geometry(self, *, content):
            if case == "decoder":
                raise RuntimeError(marker)
            if case == "dimensions":
                return DecodedGeometryMedia(
                    SourceMediaType.JPEG, 31, 24, None, 31, 24, b"\0" * (31 * 24 * 3)
                )
            return super().decode_for_geometry(content=content)

    class FaultRenderer(Renderer):
        def __init__(self, recorder):
            super().__init__(recorder)
            self.count = 0
            self.rasters: list[RenderedGeometryRaster] = []

        def render_geometry(self, *, media, quadrilateral, quarter_turn, pipeline):
            self.count += 1
            target = 1 if case == "renderer-first" else 2
            if case.startswith("renderer") and self.count == target:
                raise RuntimeError(marker)
            raster = super().render_geometry(
                media=media,
                quadrilateral=quadrilateral,
                quarter_turn=quarter_turn,
                pipeline=pipeline,
            )
            self.rasters.append(raster)
            return raster

    storage = FaultStorage(calls)
    renderer = FaultRenderer(calls)
    with pytest.raises(ImageGeometryError) as caught:
        _invoke(
            value,
            factory,
            storage=storage,
            decoder=FaultDecoder(calls),
            renderer=renderer,
        )
    assert caught.value.code is expected
    _assert_private(caught.value, marker)
    _assert_no_write_started(read, write)
    assert storage.published == 0
    if case == "renderer-second":
        assert renderer.count == 2 and len(renderer.rasters) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("source-removed", id="source-removed"),
        pytest.param("source-changed", id="source-changed"),
        pytest.param("artifact-removed", id="artifact-removed"),
        pytest.param("artifact-changed", id="artifact-changed"),
    ],
)
def test_source_and_artifact_stale_state_rolls_back_before_any_add(mutation) -> None:
    marker = f"private-phase3-marker-{mutation}"
    recipe = valid_geometry_recipe()
    factory = Factory(recipe)
    read, write = factory.units
    if mutation == "source-removed":
        write.source_files = Repo()
    elif mutation == "source-changed":
        source = next(iter(read.source_files.committed.values()))
        write.source_files = Repo((replace(source, width=31),))
    elif mutation == "artifact-removed":
        write.stored_artifacts = Repo()
    else:
        artifact = next(iter(read.stored_artifacts.committed.values()))
        write.stored_artifacts = Repo((replace(artifact, key_version=2),))
    calls: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        confirm_document_regions(
            command(recipe),
            storage=Storage(calls),
            decoder=Decoder(calls),
            renderer=Renderer(calls),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.PERSISTED_DATA_INVALID
    _assert_private(caught.value, marker)
    assert calls == ["storage.read", "decode", "render"]
    _assert_write_rejected(write)


@pytest.mark.parametrize(
    "target",
    [
        pytest.param("region-set", id="region-set-id"),
        pytest.param("set-audit", id="set-audit-id"),
        pytest.param("recipe-1", id="first-recipe-id"),
        pytest.param("recipe-audit-1", id="first-recipe-audit-id"),
        pytest.param("recipe-2", id="second-recipe-id"),
        pytest.param("recipe-audit-2", id="second-recipe-audit-id"),
    ],
)
def test_write_preflight_detects_each_new_persistent_id_before_add(target) -> None:
    value = _two_new_command()
    factory = Factory()
    write = factory.units[1]
    if target == "region-set":
        key = value.region_set_version_id
        write.document_region_sets = Repo((SimpleNamespace(region_set_version_id=key),))
    elif target == "set-audit":
        key = value.region_set_audit_event_id
        write.audit_events = Repo((SimpleNamespace(event_id=key),))
    else:
        index = 0 if target.endswith("1") else 1
        selection = value.members[index].recipe_selection
        if target.startswith("recipe-audit"):
            key = selection.recipe_audit_event_id
            write.audit_events = Repo((SimpleNamespace(event_id=key),))
        else:
            key = selection.recipe_version_id
            collision = replace(
                valid_geometry_recipe(),
                recipe_version_id=key,
                region_id=value.members[index].region_id,
            )
            write.image_geometry_recipes = Repo((collision,))
    committed = tuple(dict(repo.committed) for repo in write._repositories())
    with pytest.raises(DocumentRegionsError) as caught:
        _invoke(value, factory)
    assert caught.value.code is DocumentRegionErrorCode.IDENTITY_CONFLICT
    assert str(key) not in str(caught.value) and str(key) not in repr(caught.value)
    _assert_write_rejected(write)
    assert key in (
        write.document_region_sets.get_calls
        + write.audit_events.get_calls
        + write.image_geometry_recipes.get_calls
    )
    assert tuple(repo.committed for repo in write._repositories()) == committed


@dataclass(frozen=True, slots=True)
class StageCase:
    stage: str
    failure: str
    expected: DocumentRegionErrorCode


STAGE_CASES = (
    StageCase("recipe-1", "exists", DocumentRegionErrorCode.PERSISTENCE_CONFLICT),
    StageCase("recipe-1", "constraint", DocumentRegionErrorCode.PERSISTENCE_FAILED),
    StageCase("recipe-2", "runtime", DocumentRegionErrorCode.PERSISTENCE_FAILED),
    StageCase("audit-1", "exists", DocumentRegionErrorCode.PERSISTENCE_CONFLICT),
    StageCase("audit-2", "constraint", DocumentRegionErrorCode.PERSISTENCE_FAILED),
    StageCase("set-audit", "runtime", DocumentRegionErrorCode.PERSISTENCE_FAILED),
    StageCase("set", "exists", DocumentRegionErrorCode.PERSISTENCE_CONFLICT),
    StageCase("set", "constraint", DocumentRegionErrorCode.PERSISTENCE_FAILED),
    StageCase("set", "runtime", DocumentRegionErrorCode.PERSISTENCE_FAILED),
)


def _stage_exception(case: StageCase, marker: str) -> BaseException:
    if case.failure == "exists":
        return PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
    if case.failure == "constraint":
        return PersistenceError(PersistenceErrorCode.PERSISTENCE_CONSTRAINT)
    return RuntimeError(marker)


@pytest.mark.parametrize("case", STAGE_CASES, ids=lambda item: f"{item.stage}-{item.failure}")
def test_each_persistence_stage_failure_is_private_and_atomic(case: StageCase) -> None:
    marker = f"private-phase3-marker-{case.stage}-{case.failure}"
    value = _two_new_command()
    factory = Factory()
    write = factory.units[1]
    before = tuple(dict(repo.committed) for repo in write._repositories())
    trace: list[str] = []
    recipe_add = write.image_geometry_recipes.add
    audit_add = write.audit_events.add
    set_add = write.document_region_sets.add
    counts = {"recipe": 0, "audit": 0}

    def add_recipe(item):
        counts["recipe"] += 1
        label = f"recipe-{counts['recipe']}"
        trace.append(label)
        if case.stage == label:
            raise _stage_exception(case, marker)
        recipe_add(item)

    def add_audit(item):
        counts["audit"] += 1
        label = "set-audit" if counts["audit"] == 3 else f"audit-{counts['audit']}"
        trace.append(label)
        if case.stage == label:
            raise _stage_exception(case, marker)
        audit_add(item)

    def add_set(item):
        trace.append("set")
        if case.stage == "set":
            raise _stage_exception(case, marker)
        set_add(item)

    write.image_geometry_recipes.add = add_recipe
    write.audit_events.add = add_audit
    write.document_region_sets.add = add_set
    with pytest.raises(DocumentRegionsError) as caught:
        _invoke(value, factory)
    assert caught.value.code is case.expected
    _assert_private(caught.value, marker)
    assert trace[-1] == case.stage
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repo.pending == {} for repo in write._repositories())
    assert tuple(repo.committed for repo in write._repositories()) == before


def test_commit_failure_is_private_and_restores_all_pending_state() -> None:
    marker = "private-phase3-marker-commit"
    factory = Factory()
    write = factory.units[1]
    before = tuple(dict(repo.committed) for repo in write._repositories())

    def fail_commit():
        raise RuntimeError(marker)

    write.commit = fail_commit
    with pytest.raises(DocumentRegionsError) as caught:
        _invoke(_two_new_command(), factory)
    assert caught.value.code is DocumentRegionErrorCode.COMMIT_FAILED
    _assert_private(caught.value, marker)
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repo.pending == {} for repo in write._repositories())
    assert tuple(repo.committed for repo in write._repositories()) == before


@pytest.mark.parametrize(
    "boundary",
    [
        pytest.param("read-factory", id="read-factory"),
        pytest.param("read-enter", id="read-enter"),
        pytest.param("write-factory", id="write-factory"),
        pytest.param("write-enter", id="write-enter"),
    ],
)
def test_uow_boundary_failures_are_controlled_private_and_non_mutating(boundary) -> None:
    marker = f"private-phase3-marker-{boundary}"
    read, write = Uow((valid_geometry_recipe(),)), Uow((valid_geometry_recipe(),))
    calls: list[str] = []

    class EnterFailure:
        def __enter__(self):
            raise RuntimeError(marker)

        def __exit__(self, *_args):
            return False

    class BoundaryFactory:
        count = 0

        def unit_of_work(self):
            self.count += 1
            if boundary == "read-factory" and self.count == 1:
                raise RuntimeError(marker)
            if boundary == "read-enter" and self.count == 1:
                return EnterFailure()
            if boundary == "write-factory" and self.count == 2:
                raise RuntimeError(marker)
            if boundary == "write-enter" and self.count == 2:
                return EnterFailure()
            return read if self.count == 1 else write

    factory = BoundaryFactory()
    with pytest.raises(DocumentRegionsError) as caught:
        confirm_document_regions(
            command(valid_geometry_recipe()),
            storage=Storage(calls),
            decoder=Decoder(calls),
            renderer=Renderer(calls),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.PERSISTENCE_FAILED
    _assert_private(caught.value, marker)
    assert write.commits == 0
    assert all(repo.add_calls == [] and repo.pending == {} for repo in write._repositories())
    if boundary.startswith("write"):
        assert calls == ["storage.read", "decode", "render"]
