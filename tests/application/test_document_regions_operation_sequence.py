from dataclasses import dataclass, field
from enum import Enum, auto

import pytest

from document_intake.application.dto.document_regions import ConfirmDocumentRegionsResult
from document_intake.application.services import document_region_persistence as persistence
from document_intake.application.services import document_regions as service
from document_intake.domain.enums import AuditAction
from tests.support import pr012_application as support


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


def assert_exact_operation_trace(observed: tuple[RegionOperation, ...]) -> None:
    assert observed == EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE


def _successful_observed_execution(monkeypatch):  # noqa: C901
    state = support._expand_one_to_two(
        support._confirm_first_existing_a3(support._build_synthetic_post_migration_a_lineage())
    )
    command = support._revise_both_command(state)
    factory = support._revise_both_factory(state)
    read, write = tuple(factory.units)
    recorder = OperationRecorder()
    media_items: list[str] = []
    write_items: list[str] = []
    record_geometry_items = False
    quadrilateral_labels = {
        command.members[0].recipe_selection.quadrilateral: "A",
        command.members[1].recipe_selection.quadrilateral: "C",
    }

    original_1 = service._validate_source_independent_command

    def observe_1(*args, **kwargs):
        recorder.record(RegionOperation.VALIDATE_SOURCE_INDEPENDENT_COMMAND)
        return original_1(*args, **kwargs)

    monkeypatch.setattr(service, "_validate_source_independent_command", observe_1)
    original_2 = service._validate_region_count

    def observe_2(*args, **kwargs):
        recorder.record(RegionOperation.VALIDATE_REGION_COUNT)
        return original_2(*args, **kwargs)

    monkeypatch.setattr(service, "_validate_region_count", observe_2)
    original_3 = service._validate_contiguous_order_indices

    def observe_3(*args, **kwargs):
        recorder.record(RegionOperation.VALIDATE_CONTIGUOUS_ORDER_INDICES)
        return original_3(*args, **kwargs)

    monkeypatch.setattr(service, "_validate_contiguous_order_indices", observe_3)
    original_4 = service._validate_created_record_id_distinctness

    def observe_4(*args, **kwargs):
        recorder.record(RegionOperation.VALIDATE_CREATED_RECORD_ID_DISTINCTNESS)
        return original_4(*args, **kwargs)

    monkeypatch.setattr(service, "_validate_created_record_id_distinctness", observe_4)
    original_5 = service._validate_exactly_one_selection_form

    def observe_5(*args, **kwargs):
        recorder.record(RegionOperation.VALIDATE_EXACTLY_ONE_SELECTION_FORM)
        return original_5(*args, **kwargs)

    monkeypatch.setattr(service, "_validate_exactly_one_selection_form", observe_5)
    original_6 = service._validate_new_revision_region_identity

    def observe_6(*args, **kwargs):
        recorder.record(RegionOperation.VALIDATE_NEW_REVISION_REGION_IDENTITY)
        return original_6(*args, **kwargs)

    monkeypatch.setattr(service, "_validate_new_revision_region_identity", observe_6)
    original_7 = service._reject_command_level_duplicates

    def observe_7(*args, **kwargs):
        recorder.record(RegionOperation.REJECT_COMMAND_LEVEL_DUPLICATES)
        return original_7(*args, **kwargs)

    monkeypatch.setattr(service, "_reject_command_level_duplicates", observe_7)

    original_enter = support.Uow.__enter__

    def observe_enter(self):
        recorder.record(
            RegionOperation.ENTER_READ_UOW if self is read else RegionOperation.ENTER_WRITE_UOW
        )
        return original_enter(self)

    monkeypatch.setattr(support.Uow, "__enter__", observe_enter)

    original_9 = service._load_source

    def observe_9(*args, **kwargs):
        recorder.record(RegionOperation.LOAD_SOURCE_FILE)
        return original_9(*args, **kwargs)

    monkeypatch.setattr(service, "_load_source", observe_9)
    original_10 = service._load_original_artifact

    def observe_10(*args, **kwargs):
        recorder.record(RegionOperation.LOAD_ORIGINAL_STORED_ARTIFACT)
        return original_10(*args, **kwargs)

    monkeypatch.setattr(service, "_load_original_artifact", observe_10)
    original_11 = service._load_preceding_set

    def observe_11(*args, **kwargs):
        recorder.record(RegionOperation.LOAD_PRECEDING_REGION_SET)
        return original_11(*args, **kwargs)

    monkeypatch.setattr(service, "_load_preceding_set", observe_11)
    original_12 = service._load_selected_existing_recipes

    def observe_12(*args, **kwargs):
        recorder.record(RegionOperation.LOAD_SELECTED_EXISTING_RECIPES)
        return original_12(*args, **kwargs)

    monkeypatch.setattr(service, "_load_selected_existing_recipes", observe_12)
    original_13 = service._load_new_revision_state

    def observe_13(*args, **kwargs):
        recorder.record(RegionOperation.LOAD_NEW_REVISION_PREDECESSORS_AND_LATEST)
        return original_13(*args, **kwargs)

    monkeypatch.setattr(service, "_load_new_revision_state", observe_13)

    original_exit = support.Uow.__exit__

    def observe_exit(self, *args):
        recorder.record(
            RegionOperation.EXIT_READ_UOW_WITHOUT_COMMIT
            if self is read
            else RegionOperation.EXIT_WRITE_UOW
        )
        return original_exit(self, *args)

    monkeypatch.setattr(support.Uow, "__exit__", observe_exit)

    original_15 = service._read_immutable_original_bytes

    def observe_15(*args, **kwargs):
        recorder.record(RegionOperation.READ_IMMUTABLE_ORIGINAL_BYTES)
        return original_15(*args, **kwargs)

    monkeypatch.setattr(service, "_read_immutable_original_bytes", observe_15)
    original_16 = service._verify_integrity_contract

    def observe_16(*args, **kwargs):
        recorder.record(RegionOperation.VERIFY_CHECKSUM_AND_BYTE_INTEGRITY)
        return original_16(*args, **kwargs)

    monkeypatch.setattr(service, "_verify_integrity_contract", observe_16)
    original_17 = service._decode_source_once

    def observe_17(*args, **kwargs):
        recorder.record(RegionOperation.DECODE_SOURCE_ONCE)
        return original_17(*args, **kwargs)

    monkeypatch.setattr(service, "_decode_source_once", observe_17)
    original_18 = service._apply_exif_orientation_once

    def observe_18(*args, **kwargs):
        recorder.record(RegionOperation.APPLY_EXIF_ORIENTATION_ONCE)
        return original_18(*args, **kwargs)

    monkeypatch.setattr(service, "_apply_exif_orientation_once", observe_18)
    original_19 = service._verify_effective_dimensions

    def observe_19(*args, **kwargs):
        recorder.record(RegionOperation.VERIFY_EFFECTIVE_DIMENSIONS)
        return original_19(*args, **kwargs)

    monkeypatch.setattr(service, "_verify_effective_dimensions", observe_19)
    original_20 = service._validate_all_selected_geometry

    def observe_20(*args, **kwargs):
        nonlocal record_geometry_items
        recorder.record(RegionOperation.VALIDATE_COMPLETE_SELECTED_GEOMETRY)
        record_geometry_items = True
        try:
            return original_20(*args, **kwargs)
        finally:
            record_geometry_items = False

    monkeypatch.setattr(service, "_validate_all_selected_geometry", observe_20)
    original_21 = service._derive_all_output_dimensions

    def observe_21(*args, **kwargs):
        recorder.record(RegionOperation.DERIVE_OUTPUT_DIMENSIONS)
        return original_21(*args, **kwargs)

    monkeypatch.setattr(service, "_derive_all_output_dimensions", observe_21)
    original_22 = service._render_all_selected

    def observe_22(*args, **kwargs):
        recorder.record(RegionOperation.RENDER_COMPLETE_SELECTED_SET)
        return original_22(*args, **kwargs)

    monkeypatch.setattr(service, "_render_all_selected", observe_22)
    original_23 = service._discard_ephemeral_rasters

    def observe_23(*args, **kwargs):
        recorder.record(RegionOperation.DISCARD_EPHEMERAL_RASTERS)
        return original_23(*args, **kwargs)

    monkeypatch.setattr(service, "_discard_ephemeral_rasters", observe_23)

    original_validate = service.SourceQuadrilateral.validate_for_source

    def validate_item(self, *args, **kwargs):
        if record_geometry_items:
            media_items.append(f"VALIDATE:{quadrilateral_labels[self]}")
        return original_validate(self, *args, **kwargs)

    monkeypatch.setattr(service.SourceQuadrilateral, "validate_for_source", validate_item)
    original_derive = service.derive_geometry_dimensions

    def derive_item(quadrilateral, quarter_turn):
        media_items.append(f"DERIVE:{quadrilateral_labels[quadrilateral]}")
        return original_derive(quadrilateral, quarter_turn)

    monkeypatch.setattr(service, "derive_geometry_dimensions", derive_item)
    original_render = support.Renderer.render_geometry

    def render_item(self, *, media, quadrilateral, quarter_turn, pipeline):
        media_items.append(f"RENDER:{quadrilateral_labels[quadrilateral]}")
        return original_render(
            self,
            media=media,
            quadrilateral=quadrilateral,
            quarter_turn=quarter_turn,
            pipeline=pipeline,
        )

    monkeypatch.setattr(support.Renderer, "render_geometry", render_item)

    original_25 = service._reread_source_and_artifact

    def observe_25(*args, **kwargs):
        recorder.record(RegionOperation.REREAD_SOURCE_AND_ARTIFACT)
        return original_25(*args, **kwargs)

    monkeypatch.setattr(service, "_reread_source_and_artifact", observe_25)
    original_26 = service._reread_and_revalidate_selected_state

    def observe_26(*args, **kwargs):
        recorder.record(RegionOperation.REREAD_SET_RECIPES_PREDECESSORS_AND_LATEST)
        return original_26(*args, **kwargs)

    monkeypatch.setattr(service, "_reread_and_revalidate_selected_state", observe_26)
    original_27 = service._verify_absent_ids

    def observe_27(*args, **kwargs):
        recorder.record(RegionOperation.VERIFY_NEW_PERSISTENT_IDS_ABSENT)
        return original_27(*args, **kwargs)

    monkeypatch.setattr(service, "_verify_absent_ids", observe_27)
    original_28 = service._verify_set_revision

    def observe_28(*args, **kwargs):
        recorder.record(RegionOperation.VERIFY_SET_REVISION_AND_IMMEDIATE_PREDECESSOR)
        return original_28(*args, **kwargs)

    monkeypatch.setattr(service, "_verify_set_revision", observe_28)
    original_29 = service._verify_region_revisions

    def observe_29(*args, **kwargs):
        recorder.record(RegionOperation.VERIFY_REGION_REVISIONS_AND_IMMEDIATE_PREDECESSORS)
        return original_29(*args, **kwargs)

    monkeypatch.setattr(service, "_verify_region_revisions", observe_29)

    original_30 = persistence.add_new_geometry_recipes

    def observe_30(*args, **kwargs):
        recorder.record(RegionOperation.ADD_NEW_GEOMETRY_RECIPES_IN_ORDER)
        return original_30(*args, **kwargs)

    monkeypatch.setattr(persistence, "add_new_geometry_recipes", observe_30)
    original_31 = persistence.add_recipe_audits

    def observe_31(*args, **kwargs):
        recorder.record(RegionOperation.ADD_RECIPE_AUDITS_IN_ORDER)
        return original_31(*args, **kwargs)

    monkeypatch.setattr(persistence, "add_recipe_audits", observe_31)
    original_32 = persistence.add_region_set_version

    def observe_32(*args, **kwargs):
        recorder.record(RegionOperation.ADD_REGION_SET_VERSION)
        return original_32(*args, **kwargs)

    monkeypatch.setattr(persistence, "add_region_set_version", observe_32)
    original_34 = persistence.add_region_set_audit

    def observe_34(*args, **kwargs):
        recorder.record(RegionOperation.ADD_REGION_SET_AUDIT)
        return original_34(*args, **kwargs)

    monkeypatch.setattr(persistence, "add_region_set_audit", observe_34)

    original_recipe_add = write.image_geometry_recipes.add

    def add_recipe(item):
        write_items.append(f"ADD_RECIPE:{item.recipe_version_id}")
        return original_recipe_add(item)

    write.image_geometry_recipes.add = add_recipe
    original_audit_add = write.audit_events.add

    def add_audit(item):
        label = (
            "ADD_SET_AUDIT"
            if item.action_code is AuditAction.DOCUMENT_REGION_SET_CONFIRMED
            else f"ADD_RECIPE_AUDIT:{item.subject_id}"
        )
        write_items.append(label)
        return original_audit_add(item)

    write.audit_events.add = add_audit
    original_set_add = write.document_region_sets.add

    def add_set(item):
        write_items.append("ADD_REGION_SET")
        recorder.record(RegionOperation.ADD_ORDERED_MEMBERSHIPS)
        for member in item.members:
            write_items.append(
                f"ADD_MEMBERSHIP:{member.order_index}:{member.geometry_recipe_version_id}"
            )
        return original_set_add(item)

    write.document_region_sets.add = add_set

    original_commit = support.Uow.commit

    def observe_commit(self):
        recorder.record(RegionOperation.COMMIT_EXACTLY_ONCE)
        write_items.append("COMMIT")
        return original_commit(self)

    monkeypatch.setattr(support.Uow, "commit", observe_commit)
    original_37 = service._construct_confirmation_result

    def observe_37(*args, **kwargs):
        recorder.record(RegionOperation.CONSTRUCT_AND_RETURN_RESULT)
        return original_37(*args, **kwargs)

    monkeypatch.setattr(service, "_construct_confirmation_result", observe_37)

    result, _calls = support.run(command, factory)
    return recorder, media_items, write_items, result, read, write


def test_confirm_document_regions_exact_37_step_trace(monkeypatch) -> None:
    recorder, media_items, write_items, result, read, write = _successful_observed_execution(
        monkeypatch
    )
    assert_exact_operation_trace(tuple(recorder.observed))
    assert len(recorder.observed) == 37
    assert len(set(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE)) == 37
    assert read.commits == 0 and write.commits == 1
    assert isinstance(result, ConfirmDocumentRegionsResult)
    assert result.region_set == write.document_region_sets.add_calls[0]
    assert result.selected_recipes == tuple(write.image_geometry_recipes.add_calls)
    assert media_items == [
        "VALIDATE:A",
        "VALIDATE:C",
        "DERIVE:A",
        "DERIVE:C",
        "RENDER:A",
        "RENDER:C",
    ]
    a4, c2 = result.selected_recipes
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
    recorder, *_rest = _successful_observed_execution(monkeypatch)
    changed = list(recorder.observed)
    if mutation == "omit":
        changed.pop(18)
    elif mutation == "duplicate":
        changed.insert(18, changed[18])
    else:
        changed[18], changed[19] = changed[19], changed[18]
    with pytest.raises(AssertionError):
        assert_exact_operation_trace(tuple(changed))
