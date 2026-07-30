from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, auto
from hashlib import sha256

import pytest

from document_intake.application.dto.document_regions import (
    ConfirmDocumentRegionsCommand,
    ExistingRecipeSelection,
    RegionSetMemberInput,
)
from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.media import DecodedGeometryMedia, RenderedGeometryRaster
from document_intake.application.services import document_region_media as media_service
from document_intake.application.services import document_region_persistence as persistence
from document_intake.application.services import document_region_validation as validation
from document_intake.application.services import document_regions as service
from document_intake.application.services.image_geometry import ImageGeometryError
from document_intake.domain.enums import ArtifactKind, AuditAction, SourceMediaType
from document_intake.domain.image_geometry import GeometryErrorCode
from tests.support import pr012_application as support
from tests.support.pr011 import entity_id, valid_original_stored_artifact, valid_source_file


class RegionOperation(Enum):
    VALIDATE_SOURCE_INDEPENDENT_COMMAND = auto()
    VALIDATE_REGION_COUNT = auto()
    VALIDATE_CONTIGUOUS_ORDER_INDICES = auto()
    VALIDATE_CREATED_RECORD_ID_DISTINCTNESS = auto()
    VALIDATE_EXACTLY_ONE_SELECTION_FORM = auto()
    VALIDATE_NEW_REVISION_REGION_IDENTITY = auto()
    REJECT_COMMAND_LEVEL_DUPLICATES = auto()
    ENTER_READ_UOW = auto()
    LOAD_SOURCE_FILE = auto()
    LOAD_ORIGINAL_STORED_ARTIFACT = auto()
    LOAD_PRECEDING_REGION_SET = auto()
    LOAD_SELECTED_EXISTING_RECIPES = auto()
    LOAD_NEW_REVISION_PREDECESSORS_AND_LATEST = auto()
    EXIT_READ_UOW_WITHOUT_COMMIT = auto()
    READ_IMMUTABLE_ORIGINAL_BYTES = auto()
    VERIFY_CHECKSUM_AND_BYTE_INTEGRITY = auto()
    DECODE_SOURCE_ONCE = auto()
    APPLY_EXIF_ORIENTATION_ONCE = auto()
    VERIFY_EFFECTIVE_DIMENSIONS = auto()
    VALIDATE_COMPLETE_SELECTED_GEOMETRY = auto()
    DERIVE_OUTPUT_DIMENSIONS = auto()
    RENDER_COMPLETE_SELECTED_SET = auto()
    DISCARD_EPHEMERAL_RASTERS = auto()
    ENTER_WRITE_UOW = auto()
    REREAD_SOURCE_AND_ARTIFACT = auto()
    REREAD_SET_RECIPES_PREDECESSORS_AND_LATEST = auto()
    VERIFY_NEW_PERSISTENT_IDS_ABSENT = auto()
    VERIFY_SET_REVISION_AND_IMMEDIATE_PREDECESSOR = auto()
    VERIFY_REGION_REVISIONS_AND_IMMEDIATE_PREDECESSORS = auto()
    ADD_NEW_GEOMETRY_RECIPES_IN_ORDER = auto()
    ADD_RECIPE_AUDITS_IN_ORDER = auto()
    ADD_REGION_SET_VERSION = auto()
    ADD_ORDERED_MEMBERSHIPS = auto()
    ADD_REGION_SET_AUDIT = auto()
    COMMIT_EXACTLY_ONCE = auto()
    EXIT_WRITE_UOW = auto()
    CONSTRUCT_AND_RETURN_RESULT = auto()


EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE = (
    RegionOperation.VALIDATE_SOURCE_INDEPENDENT_COMMAND,
    RegionOperation.VALIDATE_REGION_COUNT,
    RegionOperation.VALIDATE_CONTIGUOUS_ORDER_INDICES,
    RegionOperation.VALIDATE_CREATED_RECORD_ID_DISTINCTNESS,
    RegionOperation.VALIDATE_EXACTLY_ONE_SELECTION_FORM,
    RegionOperation.VALIDATE_NEW_REVISION_REGION_IDENTITY,
    RegionOperation.REJECT_COMMAND_LEVEL_DUPLICATES,
    RegionOperation.ENTER_READ_UOW,
    RegionOperation.LOAD_SOURCE_FILE,
    RegionOperation.LOAD_ORIGINAL_STORED_ARTIFACT,
    RegionOperation.LOAD_PRECEDING_REGION_SET,
    RegionOperation.LOAD_SELECTED_EXISTING_RECIPES,
    RegionOperation.LOAD_NEW_REVISION_PREDECESSORS_AND_LATEST,
    RegionOperation.EXIT_READ_UOW_WITHOUT_COMMIT,
    RegionOperation.READ_IMMUTABLE_ORIGINAL_BYTES,
    RegionOperation.VERIFY_CHECKSUM_AND_BYTE_INTEGRITY,
    RegionOperation.DECODE_SOURCE_ONCE,
    RegionOperation.APPLY_EXIF_ORIENTATION_ONCE,
    RegionOperation.VERIFY_EFFECTIVE_DIMENSIONS,
    RegionOperation.VALIDATE_COMPLETE_SELECTED_GEOMETRY,
    RegionOperation.DERIVE_OUTPUT_DIMENSIONS,
    RegionOperation.RENDER_COMPLETE_SELECTED_SET,
    RegionOperation.DISCARD_EPHEMERAL_RASTERS,
    RegionOperation.ENTER_WRITE_UOW,
    RegionOperation.REREAD_SOURCE_AND_ARTIFACT,
    RegionOperation.REREAD_SET_RECIPES_PREDECESSORS_AND_LATEST,
    RegionOperation.VERIFY_NEW_PERSISTENT_IDS_ABSENT,
    RegionOperation.VERIFY_SET_REVISION_AND_IMMEDIATE_PREDECESSOR,
    RegionOperation.VERIFY_REGION_REVISIONS_AND_IMMEDIATE_PREDECESSORS,
    RegionOperation.ADD_NEW_GEOMETRY_RECIPES_IN_ORDER,
    RegionOperation.ADD_RECIPE_AUDITS_IN_ORDER,
    RegionOperation.ADD_REGION_SET_VERSION,
    RegionOperation.ADD_ORDERED_MEMBERSHIPS,
    RegionOperation.ADD_REGION_SET_AUDIT,
    RegionOperation.COMMIT_EXACTLY_ONCE,
    RegionOperation.EXIT_WRITE_UOW,
    RegionOperation.CONSTRUCT_AND_RETURN_RESULT,
)


@dataclass(slots=True)
class OperationRecorder:
    observed: list[RegionOperation] = field(default_factory=list)

    def record(self, operation: RegionOperation) -> None:
        self.observed.append(operation)


@dataclass(slots=True)
class RecordingStorage:
    recorder: OperationRecorder
    expected_record: StoredArtifactRecord
    source_artifact_id: object
    plaintext: bytes
    corrupt: bool = False
    read_calls: int = 0
    integrity_completions: int = 0
    publish_calls: int = 0

    def read_bytes(self, *, expected: StoredArtifactRecord) -> bytes:
        self.read_calls += 1
        self.recorder.record(RegionOperation.READ_IMMUTABLE_ORIGINAL_BYTES)
        assert expected is self.expected_record
        assert expected.artifact_id == self.source_artifact_id
        assert expected.artifact_kind is ArtifactKind.ORIGINAL
        assert expected.object_generation == 1
        returned = self.plaintext + (b"!" if self.corrupt else b"")
        if len(returned) != expected.plaintext_length:
            raise ValueError("synthetic-integrity-length")
        if sha256(returned).hexdigest() != expected.plaintext_sha256:
            raise ValueError("synthetic-integrity-sha256")
        self.integrity_completions += 1
        self.recorder.record(RegionOperation.VERIFY_CHECKSUM_AND_BYTE_INTEGRITY)
        return returned

    def publish_bytes(self, **_kwargs):
        self.publish_calls += 1
        raise AssertionError("publication is forbidden")


@dataclass(slots=True)
class RecordingDecoder:
    recorder: OperationRecorder
    invalid_orientation: bool = False
    calls: int = 0
    orientation_completions: int = 0

    def decode_for_geometry(self, *, content: bytes) -> DecodedGeometryMedia:
        self.calls += 1
        self.recorder.record(RegionOperation.DECODE_SOURCE_ONCE)
        assert content
        effective_width = 31 if self.invalid_orientation else 32
        media = DecodedGeometryMedia(
            SourceMediaType.JPEG,
            24,
            32,
            6,
            effective_width,
            24,
            b"\0" * (effective_width * 24 * 3),
        )
        assert (media.encoded_width, media.encoded_height) == (24, 32)
        assert (media.effective_width, media.effective_height) == (32, 24)
        self.orientation_completions += 1
        self.recorder.record(RegionOperation.APPLY_EXIF_ORIENTATION_ONCE)
        return media


class RecordingRenderer(support.Renderer):
    def __init__(self, calls: list[str], recorder: OperationRecorder) -> None:
        super().__init__(calls)
        self.recorder = recorder
        self.rasters: list[RenderedGeometryRaster] = []

    def render_geometry(self, **kwargs):
        if not self.rasters:
            self.recorder.record(RegionOperation.RENDER_COMPLETE_SELECTED_SET)
        raster = super().render_geometry(**kwargs)
        self.rasters.append(raster)
        return raster


def assert_exact_operation_trace(observed: tuple[RegionOperation, ...]) -> None:
    assert observed == EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE


def _mixed_command(state) -> ConfirmDocumentRegionsCommand:
    a3, c1 = state.recipes[2], state.recipes[3]
    c2_id = entity_id(35)
    return ConfirmDocumentRegionsCommand(
        entity_id(68),
        a3.source_file_id,
        state.region_sets[-1].region_set_version_id,
        3,
        (
            RegionSetMemberInput(1, a3.region_id, ExistingRecipeSelection(a3.recipe_version_id)),
            RegionSetMemberInput(
                2,
                c1.region_id,
                support.new_selection(
                    c2_id,
                    entity_id(47),
                    support._changed_c_quadrilateral(),
                    revision=2,
                    predecessor=c1.recipe_version_id,
                ),
            ),
        ),
        entity_id(78),
        support.STAMP,
        support.actor(),
        None,
    )


def _mixed_fixture():
    state = support._expand_one_to_two(
        support._confirm_first_existing_a3(support._build_synthetic_post_migration_a_lineage())
    )
    command = _mixed_command(state)
    factory = support.Factory(*state.recipes[:4])
    plaintext = b"synthetic123"
    digest = sha256(plaintext).hexdigest()
    artifact = replace(
        valid_original_stored_artifact(),
        plaintext_length=len(plaintext),
        plaintext_sha256=digest,
    )
    source = replace(valid_source_file(), width=24, height=32, exif_orientation=6)
    for unit in factory.units:
        unit.source_files = support.Repo((source,))
        unit.stored_artifacts = support.Repo((artifact,))
        unit.document_region_sets = support.Repo(state.region_sets)
    return state, command, factory, source, artifact, plaintext


def _record_helper(monkeypatch, module, name, recorder, operation):
    original = getattr(module, name)

    def observed(*args, **kwargs):
        recorder.record(operation)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, observed)


def _install_exact_observers(monkeypatch, recorder, factory, command, renderer):  # noqa: C901
    read, write = tuple(factory.units)
    for name, operation in (
        (
            "validate_source_independent_command",
            RegionOperation.VALIDATE_SOURCE_INDEPENDENT_COMMAND,
        ),
        ("validate_region_count", RegionOperation.VALIDATE_REGION_COUNT),
        ("validate_contiguous_order_indices", RegionOperation.VALIDATE_CONTIGUOUS_ORDER_INDICES),
        (
            "validate_created_record_id_distinctness",
            RegionOperation.VALIDATE_CREATED_RECORD_ID_DISTINCTNESS,
        ),
        (
            "validate_exactly_one_selection_form",
            RegionOperation.VALIDATE_EXACTLY_ONE_SELECTION_FORM,
        ),
        (
            "validate_new_revision_region_identity",
            RegionOperation.VALIDATE_NEW_REVISION_REGION_IDENTITY,
        ),
        ("reject_command_level_duplicates", RegionOperation.REJECT_COMMAND_LEVEL_DUPLICATES),
    ):
        _record_helper(monkeypatch, validation, name, recorder, operation)

    original_enter = support.Uow.__enter__

    def enter(self):
        recorder.record(
            RegionOperation.ENTER_READ_UOW if self is read else RegionOperation.ENTER_WRITE_UOW
        )
        return original_enter(self)

    monkeypatch.setattr(support.Uow, "__enter__", enter)

    for name, operation in (
        ("_load_source", RegionOperation.LOAD_SOURCE_FILE),
        ("_load_original_artifact", RegionOperation.LOAD_ORIGINAL_STORED_ARTIFACT),
        ("_load_preceding_set", RegionOperation.LOAD_PRECEDING_REGION_SET),
    ):
        _record_helper(monkeypatch, service, name, recorder, operation)

    existing_id = command.members[0].recipe_selection.geometry_recipe_version_id
    new_region_id = command.members[1].region_id
    original_get = read.image_geometry_recipes.get

    def get_recipe(key):
        result = original_get(key)
        if key == existing_id:
            assert result is not None
            recorder.record(RegionOperation.LOAD_SELECTED_EXISTING_RECIPES)
        return result

    read.image_geometry_recipes.get = get_recipe
    original_latest = read.image_geometry_recipes.get_latest_by_region

    def get_latest(source_id, region_id):
        result = original_latest(source_id, region_id)
        if region_id == new_region_id:
            assert result is not None
            recorder.record(RegionOperation.LOAD_NEW_REVISION_PREDECESSORS_AND_LATEST)
        return result

    read.image_geometry_recipes.get_latest_by_region = get_latest

    original_exit = support.Uow.__exit__

    def exit_uow(self, *args):
        recorder.record(
            RegionOperation.EXIT_READ_UOW_WITHOUT_COMMIT
            if self is read
            else RegionOperation.EXIT_WRITE_UOW
        )
        return original_exit(self, *args)

    monkeypatch.setattr(support.Uow, "__exit__", exit_uow)

    for name, operation in (
        ("_verify_effective_dimensions", RegionOperation.VERIFY_EFFECTIVE_DIMENSIONS),
        ("_validate_selected_geometry", RegionOperation.VALIDATE_COMPLETE_SELECTED_GEOMETRY),
        ("_derive_output_dimensions", RegionOperation.DERIVE_OUTPUT_DIMENSIONS),
    ):
        _record_helper(monkeypatch, media_service, name, recorder, operation)

    original_media = media_service.render_selected_set

    def media_phase(*args, **kwargs):
        result = original_media(*args, **kwargs)
        assert result is None
        assert len(renderer.rasters) == 2
        recorder.record(RegionOperation.DISCARD_EPHEMERAL_RASTERS)
        return result

    monkeypatch.setattr(media_service, "render_selected_set", media_phase)

    for name, operation in (
        ("_reread_source_and_artifact", RegionOperation.REREAD_SOURCE_AND_ARTIFACT),
        (
            "_reread_and_revalidate_selected_state",
            RegionOperation.REREAD_SET_RECIPES_PREDECESSORS_AND_LATEST,
        ),
        ("_verify_absent_ids", RegionOperation.VERIFY_NEW_PERSISTENT_IDS_ABSENT),
        ("_verify_set_revision", RegionOperation.VERIFY_SET_REVISION_AND_IMMEDIATE_PREDECESSOR),
        (
            "_verify_region_revisions",
            RegionOperation.VERIFY_REGION_REVISIONS_AND_IMMEDIATE_PREDECESSORS,
        ),
    ):
        _record_helper(monkeypatch, service, name, recorder, operation)
    for name, operation in (
        ("add_new_geometry_recipes", RegionOperation.ADD_NEW_GEOMETRY_RECIPES_IN_ORDER),
        ("add_recipe_audits", RegionOperation.ADD_RECIPE_AUDITS_IN_ORDER),
        ("add_region_set_version", RegionOperation.ADD_REGION_SET_VERSION),
        ("add_region_set_audit", RegionOperation.ADD_REGION_SET_AUDIT),
    ):
        _record_helper(monkeypatch, persistence, name, recorder, operation)

    original_set_add = write.document_region_sets.add

    def add_set(item):
        assert tuple(member.order_index for member in item.members) == (1, 2)
        recorder.record(RegionOperation.ADD_ORDERED_MEMBERSHIPS)
        return original_set_add(item)

    write.document_region_sets.add = add_set
    original_commit = support.Uow.commit

    def commit(self):
        recorder.record(RegionOperation.COMMIT_EXACTLY_ONCE)
        return original_commit(self)

    monkeypatch.setattr(support.Uow, "commit", commit)
    _record_helper(
        monkeypatch,
        service,
        "_construct_confirmation_result",
        recorder,
        RegionOperation.CONSTRUCT_AND_RETURN_RESULT,
    )
    return read, write, existing_id, new_region_id


def _successful_exact_execution(monkeypatch):
    state, command, factory, source, artifact, plaintext = _mixed_fixture()
    recorder = OperationRecorder()
    storage = RecordingStorage(recorder, artifact, source.original_artifact_id, plaintext)
    decoder = RecordingDecoder(recorder)
    renderer = RecordingRenderer([], recorder)
    read, write, existing_id, new_region_id = _install_exact_observers(
        monkeypatch, recorder, factory, command, renderer
    )
    result = service.confirm_document_regions(
        command,
        decoder=decoder,
        renderer=renderer,
        storage=storage,
        unit_of_work_factory=factory,
    )
    return (
        recorder,
        result,
        read,
        write,
        storage,
        decoder,
        renderer,
        existing_id,
        new_region_id,
        state,
    )


def test_mixed_selection_exact_37_step_trace(monkeypatch) -> None:
    recorder, result, read, write, storage, decoder, renderer, existing_id, new_region_id, state = (
        _successful_exact_execution(monkeypatch)
    )
    assert_exact_operation_trace(tuple(recorder.observed))
    assert len(recorder.observed) == len(set(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE)) == 37
    assert read.image_geometry_recipes.get_calls.count(existing_id) == 1
    assert (
        read.image_geometry_recipes.get_latest_by_region_calls.count(
            (result.region_set.source_file_id, new_region_id)
        )
        == 1
    )
    assert result.selected_recipes[0] == state.recipes[2]
    assert (
        result.selected_recipes[1].superseded_recipe_version_id
        == state.recipes[3].recipe_version_id
    )
    assert read.commits == 0 and write.commits == 1
    assert storage.integrity_completions == decoder.calls == decoder.orientation_completions == 1
    assert len(renderer.rasters) == 2 and storage.publish_calls == 0
    assert recorder.observed.index(
        RegionOperation.DISCARD_EPHEMERAL_RASTERS
    ) < recorder.observed.index(RegionOperation.ENTER_WRITE_UOW)
    assert not any(isinstance(value, RenderedGeometryRaster) for value in result.selected_recipes)
    assert all(
        not isinstance(item, RenderedGeometryRaster)
        for repo in write._repositories()
        for item in repo.add_calls
    )


def test_inapplicable_selection_reads_are_not_recorded() -> None:
    state = support._expand_one_to_two(
        support._confirm_first_existing_a3(support._build_synthetic_post_migration_a_lineage())
    )
    revise_both = support._revise_both_command(state)
    read = support._revise_both_factory(state).units[0]
    recorder = OperationRecorder()
    original_get = read.image_geometry_recipes.get

    def observe_existing_get(key):
        recorder.record(RegionOperation.LOAD_SELECTED_EXISTING_RECIPES)
        return original_get(key)

    read.image_geometry_recipes.get = observe_existing_get
    service._resolve_recipe_selections(
        revise_both, read.source_files.get(revise_both.source_file_id), read
    )
    assert RegionOperation.LOAD_SELECTED_EXISTING_RECIPES not in recorder.observed
    existing = state.recipes[2]
    existing_command = support.command(existing)
    existing_read = support.Factory(existing).units[0]
    original_latest = existing_read.image_geometry_recipes.get_latest_by_region

    def observe_latest(source_id, region_id):
        recorder.record(RegionOperation.LOAD_NEW_REVISION_PREDECESSORS_AND_LATEST)
        return original_latest(source_id, region_id)

    existing_read.image_geometry_recipes.get_latest_by_region = observe_latest
    service._resolve_recipe_selections(
        existing_command, existing_read.source_files.get(existing.source_file_id), existing_read
    )
    assert existing_read.image_geometry_recipes.get_latest_by_region_calls == []
    assert RegionOperation.LOAD_NEW_REVISION_PREDECESSORS_AND_LATEST not in recorder.observed


def test_corrupted_storage_stops_before_integrity_decode_and_write() -> None:
    _state, command, factory, source, artifact, plaintext = _mixed_fixture()
    recorder = OperationRecorder()
    storage = RecordingStorage(
        recorder, artifact, source.original_artifact_id, plaintext, corrupt=True
    )
    decoder = RecordingDecoder(recorder)
    with pytest.raises(ImageGeometryError) as error:
        service.confirm_document_regions(
            command,
            decoder=decoder,
            renderer=support.Renderer([]),
            storage=storage,
            unit_of_work_factory=factory,
        )
    assert error.value.code is GeometryErrorCode.ARTIFACT_INTEGRITY_FAILED
    assert recorder.observed == [RegionOperation.READ_IMMUTABLE_ORIGINAL_BYTES]
    assert storage.integrity_completions == decoder.calls == 0
    assert len(factory.units) == 1
    assert all(repo.add_calls == [] for repo in factory.units[0]._repositories())


def test_invalid_oriented_media_has_no_orientation_completion() -> None:
    _state, command, factory, source, artifact, plaintext = _mixed_fixture()
    recorder = OperationRecorder()
    storage = RecordingStorage(recorder, artifact, source.original_artifact_id, plaintext)
    decoder = RecordingDecoder(recorder, invalid_orientation=True)
    with pytest.raises(ImageGeometryError) as error:
        service.confirm_document_regions(
            command,
            decoder=decoder,
            renderer=support.Renderer([]),
            storage=storage,
            unit_of_work_factory=factory,
        )
    assert error.value.code is GeometryErrorCode.DECODE_FAILED
    assert decoder.calls == 1 and decoder.orientation_completions == 0
    assert RegionOperation.APPLY_EXIF_ORIENTATION_ONCE not in recorder.observed
    assert len(factory.units) == 1


def test_revise_both_media_and_write_item_order(monkeypatch) -> None:
    state = support._expand_one_to_two(
        support._confirm_first_existing_a3(support._build_synthetic_post_migration_a_lineage())
    )
    command = support._revise_both_command(state)
    factory = support._revise_both_factory(state)
    write = factory.units[1]
    media_items: list[str] = []
    write_items: list[str] = []
    labels = {
        command.members[0].recipe_selection.quadrilateral: "A",
        command.members[1].recipe_selection.quadrilateral: "C",
    }
    in_media_validation = False
    original_validate_all = media_service._validate_selected_geometry

    def validate_all(*args, **kwargs):
        nonlocal in_media_validation
        in_media_validation = True
        try:
            return original_validate_all(*args, **kwargs)
        finally:
            in_media_validation = False

    monkeypatch.setattr(media_service, "_validate_selected_geometry", validate_all)
    original_validate = service.SourceQuadrilateral.validate_for_source

    def validate_item(self, *args, **kwargs):
        if in_media_validation:
            media_items.append(f"VALIDATE:{labels[self]}")
        return original_validate(self, *args, **kwargs)

    monkeypatch.setattr(service.SourceQuadrilateral, "validate_for_source", validate_item)
    original_derive = service.derive_geometry_dimensions

    def derive_item(quad, turn):
        media_items.append(f"DERIVE:{labels[quad]}")
        return original_derive(quad, turn)

    monkeypatch.setattr(service, "derive_geometry_dimensions", derive_item)
    original_render = support.Renderer.render_geometry

    def render_item(self, **kwargs):
        media_items.append(f"RENDER:{labels[kwargs['quadrilateral']]}")
        return original_render(self, **kwargs)

    monkeypatch.setattr(support.Renderer, "render_geometry", render_item)
    original_recipe_add = write.image_geometry_recipes.add

    def add_recipe(item):
        write_items.append(f"ADD_RECIPE:{item.recipe_version_id}")
        return original_recipe_add(item)

    write.image_geometry_recipes.add = add_recipe
    original_audit_add = write.audit_events.add

    def add_audit(item):
        write_items.append(
            "ADD_SET_AUDIT"
            if item.action_code is AuditAction.DOCUMENT_REGION_SET_CONFIRMED
            else f"ADD_RECIPE_AUDIT:{item.subject_id}"
        )
        return original_audit_add(item)

    write.audit_events.add = add_audit
    original_set_add = write.document_region_sets.add

    def add_set(item):
        write_items.append("ADD_REGION_SET")
        for member in item.members:
            write_items.append(
                f"ADD_MEMBERSHIP:{member.order_index}:{member.geometry_recipe_version_id}"
            )
        return original_set_add(item)

    write.document_region_sets.add = add_set
    original_commit = write.commit

    def commit():
        write_items.append("COMMIT")
        return original_commit()

    write.commit = commit
    result, _calls = support.run(command, factory)
    a4, c2 = result.selected_recipes
    assert media_items == [
        "VALIDATE:A",
        "VALIDATE:C",
        "DERIVE:A",
        "DERIVE:C",
        "RENDER:A",
        "RENDER:C",
    ]
    assert write_items == [
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


@pytest.mark.parametrize("mutation", ["omit", "duplicate", "swap"])
def test_exact_trace_assertion_rejects_mutations(monkeypatch, mutation) -> None:
    recorder, *_rest = _successful_exact_execution(monkeypatch)
    changed = list(recorder.observed)
    if mutation == "omit":
        changed.pop(18)
    elif mutation == "duplicate":
        changed.insert(18, changed[18])
    else:
        changed[18], changed[19] = changed[19], changed[18]
    with pytest.raises(AssertionError):
        assert_exact_operation_trace(tuple(changed))
