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
    command,
)


def test_different_source_composition_exact_publication_audit_and_commit() -> None:
    calls = []
    factory = Factory(calls)
    storage = Storage(calls)
    composer = Composer(calls)
    encoder = Encoder(calls)
    result = create_document_side_composition(
        command(),
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        composer=composer,
        encoder=encoder,
        storage=storage,
        unit_of_work_factory=factory,
    )
    write = factory.used[1]
    assert composer.count == encoder.count == storage.publish_calls == write.commits == 1
    assert write.document_side_compositions.add_calls == ["composition", "version", "artifact"]
    event = write.audit_events.add_calls[0]
    assert (event.action_code, event.subject_type) == (
        AuditAction.DOCUMENT_SIDE_COMPOSITION_CREATED,
        AuditSubjectType.DOCUMENT_SIDE_COMPOSITION,
    )
    assert event.before is event.after is event.field_key is event.reason_code is None
    assert calls[-2:] == ["uow.commit", "uow.exit"]
    assert result.composition_version.id == command().composition_version_id


def test_exact_operation_boundaries_encode_and_publish_once() -> None:
    calls = []
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
    assert calls.count("compose") == calls.count("encode") == calls.count("storage.publish") == 1
    assert calls.index("encode") < calls.index("storage.publish") < calls.index("uow.commit")
