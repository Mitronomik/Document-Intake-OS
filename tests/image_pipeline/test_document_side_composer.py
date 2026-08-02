import pytest
from PIL import Image

from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.domain.document_side_composition import (
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
    DocumentSideCompositionPipelineVersion,
)
from document_intake.domain.enums import DocumentSideCompositionLayout
from document_intake.image_pipeline.document_side_composer import PillowDocumentSideComposer


def raster(width: int, height: int, color: tuple[int, int, int]) -> UncompressedRgbRaster:
    return UncompressedRgbRaster(width, height, bytes(color) * (width * height))


def compose(layout: DocumentSideCompositionLayout) -> UncompressedRgbRaster:
    return PillowDocumentSideComposer().compose(
        side_1=raster(4, 2, (255, 0, 0)),
        side_2=raster(2, 4, (0, 0, 255)),
        layout=layout,
        outer_margin_px=2,
        inter_side_gap_px=1,
        pipeline=DocumentSideCompositionPipelineVersion(),
    )


def test_vertical_exact_canvas_margin_gap_order_and_no_upscale() -> None:
    result = compose(DocumentSideCompositionLayout.VERTICAL)
    assert (result.width, result.height) == (6, 10)
    image = Image.frombytes("RGB", (result.width, result.height), result.rgb_pixels)
    assert image.getpixel((0, 0)) == (255, 255, 255)
    assert image.getpixel((2, 2))[0] > image.getpixel((2, 2))[2]
    assert image.getpixel((2, 3)) == (255, 255, 255)
    assert image.getpixel((2, 4))[2] > image.getpixel((2, 4))[0]


def test_horizontal_exact_canvas_margin_gap_and_explicit_order() -> None:
    result = compose(DocumentSideCompositionLayout.HORIZONTAL)
    assert (result.width, result.height) == (10, 6)
    image = Image.frombytes("RGB", (result.width, result.height), result.rgb_pixels)
    assert image.getpixel((2, 2))[0] > image.getpixel((2, 2))[2]
    assert image.getpixel((6, 2)) == (255, 255, 255)
    assert image.getpixel((7, 2))[2] > image.getpixel((7, 2))[0]


def test_integer_half_up_and_zero_dimension_failure() -> None:
    composer = PillowDocumentSideComposer()
    result = composer.compose(
        side_1=raster(4, 3, (1, 2, 3)),
        side_2=raster(2, 2, (4, 5, 6)),
        layout=DocumentSideCompositionLayout.VERTICAL,
        outer_margin_px=0,
        inter_side_gap_px=0,
        pipeline=DocumentSideCompositionPipelineVersion(),
    )
    assert result.height == 4  # half-up(3*2/4)=2 plus unchanged 2
    with pytest.raises(DocumentSideCompositionError) as captured:
        composer.compose(
            side_1=raster(1000, 1, (1, 2, 3)),
            side_2=raster(1, 1, (4, 5, 6)),
            layout=DocumentSideCompositionLayout.VERTICAL,
            outer_margin_px=0,
            inter_side_gap_px=0,
            pipeline=DocumentSideCompositionPipelineVersion(),
        )
    assert captured.value.code is DocumentSideCompositionErrorCode.COMPOSITION_RENDER_FAILED
