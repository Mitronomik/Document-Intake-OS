from document_intake.application.services.document_side_composition import (
    create_document_side_composition,
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


def test_explicit_side_order_is_preserved() -> None:
    calls = []
    factory = Factory(calls)
    result = create_document_side_composition(
        command(swapped=True),
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        composer=Composer(calls),
        encoder=Encoder(calls),
        storage=Storage(calls),
        unit_of_work_factory=factory,
    )
    assert (
        result.composition_version.side_1_source_file_id
        == command(swapped=True).side_1.source_file_id
    )
    assert (
        result.composition_version.side_2_source_file_id
        == command(swapped=True).side_2.source_file_id
    )
