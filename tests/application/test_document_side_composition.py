import pytest

from document_intake.application.services.document_side_composition import (
    create_document_side_composition,
)
from document_intake.domain.enums import AuditAction, AuditSubjectType
from tests.support.pr013_application import (
    Composer,
    Decoder,
    Encoder,
    Factory,
    Renderer,
    Storage,
    Variant,
    command,
)


@pytest.mark.parametrize("variant", ("different_sources", "same_source", "same_region_set"))
def test_happy_path_variants_validate_both_sides_and_commit_once(variant: Variant) -> None:
    calls: list[str] = []
    factory = Factory(calls, variant=variant)
    storage = Storage(calls)
    composer = Composer(calls)
    encoder = Encoder(calls)
    selected = command(variant=variant)
    result = create_document_side_composition(
        selected,
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        composer=composer,
        encoder=encoder,
        storage=storage,
        unit_of_work_factory=factory,
    )
    read, write = factory.used
    assert composer.count == encoder.count == storage.publish_calls == write.commits == 1
    assert write.commit_attempts == 1
    assert write.committed_row_count == 5
    assert write.document_side_compositions.add_calls == ["composition", "version", "artifact"]
    assert (
        len(read.document_region_sets.get_calls) == len(write.document_region_sets.get_calls) == 2
    )
    assert (
        len(read.image_geometry_recipes.get_calls)
        == len(write.image_geometry_recipes.get_calls)
        == 2
    )
    assert result.composition_version.side_1_region_id == selected.side_1.region_id
    assert result.composition_version.side_2_region_id == selected.side_2.region_id
    assert result.composition_version.side_1_source_file_id == selected.side_1.source_file_id
    assert result.composition_version.side_2_source_file_id == selected.side_2.source_file_id
    event = write.audit_events.add_calls[0]
    assert (event.action_code, event.subject_type) == (
        AuditAction.DOCUMENT_SIDE_COMPOSITION_CREATED,
        AuditSubjectType.DOCUMENT_SIDE_COMPOSITION,
    )
    assert event.before is event.after is event.field_key is event.reason_code is None
    assert calls[-2:] == ["uow.commit", "uow.exit"]


def test_exact_operation_boundaries_encode_publish_insert_commit_and_exit_once() -> None:
    calls: list[str] = []
    factory = Factory(calls)
    create_document_side_composition(
        command(),
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        composer=Composer(calls),
        encoder=Encoder(calls),
        storage=Storage(calls),
        unit_of_work_factory=factory,
    )
    assert calls.count("decode") == calls.count("render") == 2
    assert calls.count("compose") == calls.count("encode") == 1
    assert calls.count("storage.publish") == calls.count("uow.commit") == 1
    assert calls.index("encode") < calls.index("storage.publish") < calls.index("uow.commit")
    assert calls[-1] == "uow.exit"
