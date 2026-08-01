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
from document_intake.domain.value_objects import SourceBasename
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
            RegionSetMemberInput(
                1, first.region_id, ExistingRecipeSelection(first.recipe_version_id)
            ),
            RegionSetMemberInput(
                2, second.region_id, ExistingRecipeSelection(second.recipe_version_id)
            ),
        ),
    )
    return value, first, second


def _invoke(value, factory, *, storage=None, decoder=None, renderer=None):
    calls: list[str] = []
    confirm_document_regions(
        value,
        storage=storage or Storage(calls),
        decoder=decoder or Decoder(calls),
        renderer=renderer or Renderer(calls),
        unit_of_work_factory=factory,
    )


def _first_region_set(root):
    calls: list[str] = []
    return confirm_document_regions(
        command(root),
        storage=Storage(calls),
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        unit_of_work_factory=Factory(root),
    ).region_set


def _revision_command(root, previous, *, set_revision=2):
    return replace(
        command(root),
        region_set_version_id=entity_id(62),
        region_set_audit_event_id=entity_id(63),
        superseded_region_set_version_id=previous.region_set_version_id,
        set_revision=set_revision,
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


def _assert_private(error: BaseException, marker: str) -> None:
    assert marker not in str(error)
    assert marker not in repr(error)


def _assert_private_context(error: BaseException, sensitive_value: str) -> None:
    _assert_private(error, sensitive_value)
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def _uow_repository_snapshot(uow: Uow) -> tuple[object, ...]:
    return tuple(
        (
            dict(repository.committed),
            dict(repository.pending),
            tuple(repository.add_calls),
        )
        for repository in uow._repositories()
    )


def _assert_no_repository_adds(*units: Uow) -> None:
    assert all(repository.add_calls == [] for unit in units for repository in unit._repositories())


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
    privacy_value = "31" if case == "dimensions" else marker
    _assert_private(caught.value, privacy_value)
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
    recipe = valid_geometry_recipe()
    value = command(recipe)
    factory = Factory(recipe)
    read, write = factory.units
    read_source = next(iter(read.source_files.committed.values()))
    if mutation == "source-removed":
        write.source_files = Repo()
        sensitive_value = str(value.source_file_id)
    elif mutation == "source-changed":
        basename = SourceBasename("private-phase3-source-changed.jpg")
        write.source_files = Repo((replace(read_source, original_basename=basename),))
        sensitive_value = str(basename)
    elif mutation == "artifact-removed":
        write.stored_artifacts = Repo()
        sensitive_value = str(read_source.original_artifact_id)
    else:
        artifact = next(iter(read.stored_artifacts.committed.values()))
        sensitive_value = "c" * 64
        write.stored_artifacts = Repo((replace(artifact, plaintext_sha256=sensitive_value),))
    calls: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        confirm_document_regions(
            value,
            storage=Storage(calls),
            decoder=Decoder(calls),
            renderer=Renderer(calls),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.PERSISTED_DATA_INVALID
    _assert_private_context(caught.value, sensitive_value)
    assert calls == ["storage.read", "decode", "render"]
    _assert_write_rejected(write)
    assert write.source_files.get_calls == [value.source_file_id]
    expected_artifact_calls = (
        [] if mutation.startswith("source") else [read_source.original_artifact_id]
    )
    assert write.stored_artifacts.get_calls == expected_artifact_calls
    assert write.document_region_sets.get_calls == []
    assert write.document_region_sets.get_latest_by_source_calls == []
    assert write.image_geometry_recipes.get_calls == []
    assert write.image_geometry_recipes.get_latest_by_region_calls == []
    assert write.audit_events.get_calls == []


def test_initial_missing_preceding_set_stops_before_media_and_write() -> None:
    root = valid_geometry_recipe()
    missing_id = entity_id(70)
    value = replace(
        command(root),
        region_set_version_id=entity_id(62),
        region_set_audit_event_id=entity_id(63),
        superseded_region_set_version_id=missing_id,
        set_revision=2,
    )

    class CountingFactory(Factory):
        pass

    factory = CountingFactory(root)
    read, write = factory.units
    read_before = _uow_repository_snapshot(read)
    write_before = _uow_repository_snapshot(write)
    media_calls: list[str] = []
    with pytest.raises(DocumentRegionsError) as caught:
        confirm_document_regions(
            value,
            storage=Storage(media_calls),
            decoder=Decoder(media_calls),
            renderer=Renderer(media_calls),
            unit_of_work_factory=factory,
        )
    assert caught.value.code is DocumentRegionErrorCode.REGION_SET_NOT_FOUND
    _assert_private_context(caught.value, str(missing_id))
    assert factory.calls == 1
    assert read.enters == 1 and read.exits == 1 and read.rollbacks == 1
    assert write.enters == 0 and write.commits == 0 and write.rollbacks == 0
    assert media_calls == []
    _assert_no_repository_adds(read, write)
    assert all(
        repository.pending == {} for repository in (*read._repositories(), *write._repositories())
    )
    assert _uow_repository_snapshot(read) == read_before
    assert _uow_repository_snapshot(write) == write_before


def test_changed_preceding_set_precedes_set_revision_conflict_and_id_checks() -> None:
    root = valid_geometry_recipe()
    previous = _first_region_set(root)
    value = _revision_command(root, previous, set_revision=3)
    changed_actor_id = entity_id(89)
    changed = replace(
        previous,
        confirmed_by=replace(previous.confirmed_by, actor_id=changed_actor_id),
    )
    factory = Factory(root)
    read, write = factory.units
    read.document_region_sets = Repo((previous,))
    write.document_region_sets = Repo((changed,))
    before = _uow_repository_snapshot(write)
    with pytest.raises(DocumentRegionsError) as caught:
        _invoke(value, factory)
    assert caught.value.code is DocumentRegionErrorCode.PERSISTED_DATA_INVALID
    _assert_private_context(caught.value, str(changed_actor_id))
    assert write.document_region_sets.get_calls == [previous.region_set_version_id]
    assert write.document_region_sets.get_latest_by_source_calls == [root.source_file_id]
    assert write.image_geometry_recipes.get_calls == [root.recipe_version_id]
    assert write.image_geometry_recipes.get_latest_by_region_calls == [
        (root.source_file_id, root.region_id)
    ]
    assert value.region_set_version_id not in write.document_region_sets.get_calls
    assert value.region_set_audit_event_id not in write.audit_events.get_calls
    selection = value.members[0].recipe_selection
    assert selection.recipe_version_id not in write.image_geometry_recipes.get_calls
    assert selection.recipe_audit_event_id not in write.audit_events.get_calls
    _assert_no_repository_adds(write)
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repository.pending == {} for repository in write._repositories())
    assert _uow_repository_snapshot(write) == before


def test_changed_recipe_predecessor_precedes_region_revision_conflict_and_id_checks() -> None:
    root = valid_geometry_recipe()
    previous = _first_region_set(root)
    value = _revision_command(root, previous)
    changed_time = root.created_at.replace(microsecond=123456)
    changed = replace(root, created_at=changed_time)
    advanced = replace(
        root,
        recipe_version_id=entity_id(33),
        superseded_recipe_version_id=root.recipe_version_id,
        revision=2,
    )
    factory = Factory(root)
    read, write = factory.units
    read.document_region_sets = Repo((previous,))
    write.document_region_sets = Repo((previous,))
    write.image_geometry_recipes = Repo((changed, advanced))
    before = _uow_repository_snapshot(write)
    with pytest.raises(DocumentRegionsError) as caught:
        _invoke(value, factory)
    assert caught.value.code is DocumentRegionErrorCode.PERSISTED_DATA_INVALID
    _assert_private_context(caught.value, changed_time.isoformat())
    assert write.image_geometry_recipes.get_calls == [root.recipe_version_id]
    assert write.image_geometry_recipes.get_latest_by_region_calls == [
        (root.source_file_id, root.region_id)
    ]
    assert value.region_set_version_id not in write.document_region_sets.get_calls
    assert value.region_set_audit_event_id not in write.audit_events.get_calls
    selection = value.members[0].recipe_selection
    assert selection.recipe_version_id not in write.image_geometry_recipes.get_calls
    assert selection.recipe_audit_event_id not in write.audit_events.get_calls
    _assert_no_repository_adds(write)
    assert write.commits == 0 and write.rollbacks == 1
    assert all(repository.pending == {} for repository in write._repositories())
    assert _uow_repository_snapshot(write) == before


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


class MarkedPersistenceError(PersistenceError):
    def __init__(self, code: PersistenceErrorCode, marker: str) -> None:
        super().__init__(code)
        self._marker = marker

    def __str__(self) -> str:
        return f"{super().__str__()}:{self._marker}"

    def __repr__(self) -> str:
        return f"{super().__repr__()}:{self._marker}"


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
        return MarkedPersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS, marker)
    if case.failure == "constraint":
        return MarkedPersistenceError(PersistenceErrorCode.PERSISTENCE_CONSTRAINT, marker)
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
    injected = _stage_exception(case, marker)
    assert marker in str(injected) and marker in repr(injected)

    def add_recipe(item):
        counts["recipe"] += 1
        label = f"recipe-{counts['recipe']}"
        trace.append(label)
        if case.stage == label:
            raise injected
        recipe_add(item)

    def add_audit(item):
        counts["audit"] += 1
        label = "set-audit" if counts["audit"] == 3 else f"audit-{counts['audit']}"
        trace.append(label)
        if case.stage == label:
            raise injected
        audit_add(item)

    def add_set(item):
        trace.append("set")
        if case.stage == "set":
            raise injected
        set_add(item)

    write.image_geometry_recipes.add = add_recipe
    write.audit_events.add = add_audit
    write.document_region_sets.add = add_set
    with pytest.raises(DocumentRegionsError) as caught:
        _invoke(value, factory)
    assert caught.value.code is case.expected
    _assert_private_context(caught.value, marker)
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
    _assert_private_context(caught.value, marker)
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
    read_before = _uow_repository_snapshot(read)
    write_before = _uow_repository_snapshot(write)
    calls: list[str] = []
    injected = RuntimeError(marker)
    assert marker in str(injected) and marker in repr(injected)

    class EnterFailure:
        attempts = 0

        def __enter__(self):
            self.attempts += 1
            raise injected

        def __exit__(self, *_args):
            return False

    failing_context = EnterFailure()

    class BoundaryFactory:
        count = 0

        def unit_of_work(self):
            self.count += 1
            if boundary == "read-factory" and self.count == 1:
                raise injected
            if boundary == "read-enter" and self.count == 1:
                return failing_context
            if boundary == "write-factory" and self.count == 2:
                raise injected
            if boundary == "write-enter" and self.count == 2:
                return failing_context
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
    _assert_private_context(caught.value, marker)
    expected_factory_calls = 1 if boundary.startswith("read") else 2
    assert factory.count == expected_factory_calls
    assert failing_context.attempts == (1 if boundary.endswith("enter") else 0)
    assert read.enters == (1 if boundary.startswith("write") else 0)
    assert read.exits == (1 if boundary.startswith("write") else 0)
    assert write.enters == 0
    assert write.exits == 0
    assert read.commits == 0 and write.commits == 0
    assert read.rollbacks == 0 and write.rollbacks == 0
    assert _uow_repository_snapshot(read) == read_before
    assert _uow_repository_snapshot(write) == write_before
    _assert_no_repository_adds(read, write)
    if boundary.startswith("write"):
        assert calls == ["storage.read", "decode", "render"]
    else:
        assert calls == []
