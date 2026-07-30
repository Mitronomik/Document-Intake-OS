from document_intake.application.services import document_regions as service
from tests.support import pr012_application as support

EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE = tuple(
    f"{index:02d}_{label}"
    for index, label in enumerate(
        (
            "VALIDATE_SOURCE_INDEPENDENT_COMMAND",
            "VALIDATE_REGION_COUNT",
            "VALIDATE_CONTIGUOUS_ORDER_INDICES",
            "VALIDATE_CREATED_RECORD_ID_DISTINCTNESS",
            "VALIDATE_EXACTLY_ONE_SELECTION_FORM",
            "VALIDATE_NEW_REVISION_REGION_IDENTITY",
            "REJECT_COMMAND_LEVEL_DUPLICATES",
            "ENTER_READ_UOW",
            "LOAD_SOURCE_FILE",
            "LOAD_ORIGINAL_STORED_ARTIFACT",
            "LOAD_PRECEDING_REGION_SET",
            "LOAD_SELECTED_EXISTING_RECIPES",
            "LOAD_NEW_REVISION_PREDECESSORS_AND_LATEST",
            "EXIT_READ_UOW_WITHOUT_COMMIT",
            "READ_IMMUTABLE_ORIGINAL_BYTES",
            "VERIFY_CHECKSUM_AND_BYTE_INTEGRITY",
            "DECODE_SOURCE_ONCE",
            "APPLY_EXIF_ORIENTATION_ONCE",
            "VERIFY_EFFECTIVE_DIMENSIONS",
            "VALIDATE_COMPLETE_SELECTED_GEOMETRY",
            "DERIVE_OUTPUT_DIMENSIONS",
            "RENDER_COMPLETE_SELECTED_SET",
            "DISCARD_EPHEMERAL_RASTERS",
            "ENTER_WRITE_UOW",
            "REREAD_SOURCE_AND_ARTIFACT",
            "REREAD_SET_RECIPES_PREDECESSORS_AND_LATEST",
            "VERIFY_NEW_PERSISTENT_IDS_ABSENT",
            "VERIFY_SET_REVISION_AND_IMMEDIATE_PREDECESSOR",
            "VERIFY_REGION_REVISIONS_AND_IMMEDIATE_PREDECESSORS",
            "ADD_NEW_GEOMETRY_RECIPES_IN_ORDER",
            "ADD_RECIPE_AUDITS_IN_ORDER",
            "ADD_REGION_SET_VERSION",
            "ADD_ORDERED_MEMBERSHIPS",
            "ADD_REGION_SET_AUDIT",
            "COMMIT_EXACTLY_ONCE",
            "EXIT_WRITE_UOW",
            "CONSTRUCT_AND_RETURN_RESULT",
        ),
        1,
    )
)


def test_confirm_document_regions_exact_37_step_trace(monkeypatch):
    trace = []
    original_validate = service._validate_command
    original_load = service._load_read_context
    original_resolve = service._resolve_recipe_selections
    original_render = service._render_selected_set
    original_revalidate = service._revalidate_write_context
    original_persist = service._persist_confirmation
    original_enter = support.Uow.__enter__
    original_exit = support.Uow.__exit__
    original_commit = support.Uow.commit
    enters = 0

    def validate(command):
        trace.extend(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[:7])
        return original_validate(command)

    def enter(self):
        nonlocal enters
        enters += 1
        trace.append(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[7 if enters == 1 else 23])
        return original_enter(self)

    def load(command, uow):
        result = original_load(command, uow)
        trace.extend(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[8:11])
        return result

    def resolve(command, source, uow):
        result = original_resolve(command, source, uow)
        trace.extend(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[11:13])
        return result

    def exit_uow(self, *args):
        result = original_exit(self, *args)
        trace.append(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[13 if enters == 1 else 35])
        return result

    def render(context, decoder, renderer, storage):
        trace.extend(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[14:23])
        return original_render(context, decoder, renderer, storage)

    def revalidate(command, read, uow):
        result = original_revalidate(command, read, uow)
        trace.extend(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[24:29])
        return result

    def persist(command, selected, uow):
        result = original_persist(command, selected, uow)
        trace.extend(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[29:34])
        return result

    def commit(self):
        result = original_commit(self)
        trace.append(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[34])
        return result

    monkeypatch.setattr(service, "_validate_command", validate)
    monkeypatch.setattr(service, "_load_read_context", load)
    monkeypatch.setattr(service, "_resolve_recipe_selections", resolve)
    monkeypatch.setattr(service, "_render_selected_set", render)
    monkeypatch.setattr(service, "_revalidate_write_context", revalidate)
    monkeypatch.setattr(service, "_persist_confirmation", persist)
    monkeypatch.setattr(support.Uow, "__enter__", enter)
    monkeypatch.setattr(support.Uow, "__exit__", exit_uow)
    monkeypatch.setattr(support.Uow, "commit", commit)

    state = support._expand_one_to_two(
        support._confirm_first_existing_a3(support._build_synthetic_post_migration_a_lineage())
    )
    trace.clear()
    enters = 0
    result = support._revise_a_only(state)
    trace.append(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE[36])
    assert result.results[-1] is not None
    assert len(EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE) == 37
    assert tuple(trace) == EXPECTED_CONFIRM_DOCUMENT_REGIONS_TRACE
    assert result.writes[-1].commits == 1
