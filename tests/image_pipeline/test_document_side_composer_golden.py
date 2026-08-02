from hashlib import sha256

from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.domain.document_side_composition import DocumentSideCompositionPipelineVersion
from document_intake.domain.enums import DocumentSideCompositionLayout
from document_intake.image_pipeline.document_side_composer import PillowDocumentSideComposer


def test_uncompressed_rgb_synthetic_golden() -> None:
    side_1 = UncompressedRgbRaster(3, 2, bytes(range(18)))
    side_2 = UncompressedRgbRaster(2, 3, bytes(reversed(range(18))))
    result = PillowDocumentSideComposer().compose(
        side_1=side_1,
        side_2=side_2,
        layout=DocumentSideCompositionLayout.HORIZONTAL,
        outer_margin_px=1,
        inter_side_gap_px=2,
        pipeline=DocumentSideCompositionPipelineVersion(),
    )
    assert sha256(result.rgb_pixels).hexdigest() == (
        "e8498c6d2d80a4f157eeba5105525b9c4f058143500fed6a00dc8eb33df0685b"
    )
