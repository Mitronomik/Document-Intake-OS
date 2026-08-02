import pytest

from document_intake.application.services.document_side_composition import (
    create_document_side_composition,
)
from document_intake.domain.document_side_composition import (
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
)
from tests.support.pr013_application import (
    Composer,
    Decoder,
    Encoder,
    Factory,
    Renderer,
    Storage,
    command,
)


def invoke(factory, storage):
    calls = factory.units[0].calls
    return create_document_side_composition(
        command(),
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        composer=Composer(calls),
        encoder=Encoder(calls),
        storage=storage,
        unit_of_work_factory=factory,
    )


def test_natural_key_preflight_prevents_publication() -> None:
    calls = []
    factory = Factory(calls)
    factory.units[1].document_side_compositions.natural = object()
    storage = Storage(calls)
    with pytest.raises(DocumentSideCompositionError) as captured:
        invoke(factory, storage)
    assert captured.value.code is DocumentSideCompositionErrorCode.COMPOSITION_ALREADY_EXISTS
    assert storage.publish_calls == 0


def test_stale_write_snapshot_fails_before_publication() -> None:
    calls = []
    factory = Factory(calls)
    storage = Storage(calls)
    factory.units[1].source_files.values.pop(command().side_1.source_file_id)
    with pytest.raises(DocumentSideCompositionError) as captured:
        invoke(factory, storage)
    assert captured.value.code is DocumentSideCompositionErrorCode.PERSISTED_DATA_INVALID
    assert storage.publish_calls == 0
