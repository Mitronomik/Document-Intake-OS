import pytest

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
    Variant,
    command,
)


@pytest.mark.parametrize("variant", ("different_sources", "same_source", "same_region_set"))
def test_explicit_swapped_side_order_is_preserved_for_every_valid_variant(
    variant: Variant,
) -> None:
    calls: list[str] = []
    factory = Factory(calls, variant=variant)
    selected = command(variant=variant, swapped=True)
    result = create_document_side_composition(
        selected,
        decoder=Decoder(calls),
        renderer=Renderer(calls),
        composer=Composer(calls),
        encoder=Encoder(calls),
        storage=Storage(calls),
        unit_of_work_factory=factory,
    )
    version = result.composition_version
    assert (
        version.side_1_region_set_version_id,
        version.side_1_source_file_id,
        version.side_1_region_id,
    ) == (
        selected.side_1.region_set_version_id,
        selected.side_1.source_file_id,
        selected.side_1.region_id,
    )
    assert (
        version.side_2_region_set_version_id,
        version.side_2_source_file_id,
        version.side_2_region_id,
    ) == (
        selected.side_2.region_set_version_id,
        selected.side_2.source_file_id,
        selected.side_2.region_id,
    )
    assert factory.used[1].commits == 1
