from io import BytesIO

import pytest
from PIL import Image

from document_intake.application.ports.media import DecodedQualityMedia
from document_intake.domain.enums import SourceMediaType
from document_intake.domain.errors import InvalidValueError
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder, dhash64


def png(mode="RGB"):
    img = Image.new(mode, (2, 1), (10, 20, 30, 128) if mode == "RGBA" else (10, 20, 30))
    b = BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def test_decoded_quality_media_invariants() -> None:
    DecodedQualityMedia(SourceMediaType.PNG, 2, 1, None, 2, 1, b"\x00\x01", 2, 1)
    for kwargs in [
        dict(encoded_width=True),
        dict(exif_orientation=True),
        dict(grayscale_pixels=bytearray(b"12")),
        dict(effective_width=1),
    ]:
        base = dict(
            media_type=SourceMediaType.PNG,
            encoded_width=2,
            encoded_height=1,
            exif_orientation=None,
            effective_width=2,
            effective_height=1,
            grayscale_pixels=b"12",
            grayscale_width=2,
            grayscale_height=1,
        )
        base.update(kwargs)
        with pytest.raises(InvalidValueError):
            DecodedQualityMedia(**base)


def test_quality_decoder_full_resolution_luminance_and_import_compat() -> None:
    content = png()
    before = bytes(content)
    d = PillowMediaDecoder().decode_for_quality(content=content)
    assert content == before and d.grayscale_width == 2 and d.grayscale_height == 1
    assert d.grayscale_pixels == bytes([(299 * 10 + 587 * 20 + 114 * 30 + 500) // 1000]) * 2
    imp = PillowMediaDecoder().decode_for_import(content=content)
    assert (
        imp.grayscale_width == 9 and imp.grayscale_height == 8 and len(imp.grayscale_pixels) == 72
    )
    assert len(dhash64(imp.grayscale_pixels)) == 16
