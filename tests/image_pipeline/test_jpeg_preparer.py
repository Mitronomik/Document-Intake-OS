from PIL import Image, JpegImagePlugin

from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.domain.prepared_jpeg import (
    MAX_PREPARED_JPEG_BYTES,
    PreparedJpegPipelineVersion,
)
from document_intake.image_pipeline.jpeg_preparer import (
    PillowPreparedJpegEncoder,
    _scaled_dimension,
)


def test_preparer_is_deterministic_metadata_free_rgb_jpeg() -> None:
    pixels = bytes(
        (x * 17 + y * 31 + channel * 53) % 256
        for y in range(64)
        for x in range(96)
        for channel in range(3)
    )
    raster = UncompressedRgbRaster(96, 64, pixels)
    encoder = PillowPreparedJpegEncoder()
    first = encoder.encode_prepared_jpeg(raster, pipeline=PreparedJpegPipelineVersion())
    second = encoder.encode_prepared_jpeg(raster, pipeline=PreparedJpegPipelineVersion())
    assert first == second
    assert first.byte_size <= MAX_PREPARED_JPEG_BYTES
    assert first.jpeg_quality == 95
    assert first.resize_percent == 100
    assert JpegImagePlugin.get_sampling(Image.open(__import__("io").BytesIO(first.jpeg_bytes))) == 0


def test_half_up_dimension_math() -> None:
    assert _scaled_dimension(5, 50) == 3
