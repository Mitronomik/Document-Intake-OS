from __future__ import annotations

import io
import warnings
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageOps

from document_intake.domain.enums import SourceImportErrorCode, SourceMediaType
from document_intake.image_pipeline import media_decoder
from document_intake.image_pipeline.media_decoder import (
    MediaDecodeError,
    PillowMediaDecoder,
    dhash64,
    dhash64_hamming_distance,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic" / "pr008_color_grid.heic"


@pytest.fixture(autouse=True)
def reset_heif_registration() -> None:
    media_decoder._HEIF_REGISTERED = False


def encoded(
    image: Image.Image,
    format_name: str,
    *,
    orientation: object | None = None,
    save_all: bool = False,
    append_images: list[Image.Image] | None = None,
) -> bytes:
    stream = io.BytesIO()
    exif = Image.Exif()
    if orientation is not None:
        exif[274] = orientation
    kwargs: dict[str, object] = {}
    if orientation is not None:
        kwargs["exif"] = exif
    if save_all:
        kwargs["save_all"] = True
        kwargs["append_images"] = append_images or []
    image.save(stream, format=format_name, **kwargs)
    return stream.getvalue()


def decode(content: bytes):  # type: ignore[no-untyped-def]
    return PillowMediaDecoder().decode_for_import(content=content)


def test_dhash64_vectors_distance_leading_zero_and_invalid_raster() -> None:
    ascending = bytes([0, 16, 32, 48, 64, 80, 96, 112, 128] * 8)
    descending = bytes([128, 112, 96, 80, 64, 48, 32, 16, 0] * 8)
    alternating = bytes(
        [
            0,
            16,
            32,
            48,
            64,
            80,
            96,
            112,
            128,
            128,
            112,
            96,
            80,
            64,
            48,
            32,
            16,
            0,
        ]
        * 4
    )
    assert dhash64(ascending) == "0000000000000000"
    assert dhash64(descending) == "ffffffffffffffff"
    assert dhash64(alternating) == "00ff00ff00ff00ff"
    assert len(dhash64(ascending)) == 16
    assert dhash64_hamming_distance("0000000000000000", "ffffffffffffffff") == 64
    assert dhash64_hamming_distance("0000000000000000", "00ff00ff00ff00ff") == 32
    assert dhash64_hamming_distance("0000000000000000", "0000000000000001") == 1
    with pytest.raises(ValueError, match="ERR_IMPORT_DECODED_RASTER_INVALID"):
        dhash64(b"short")


def test_generated_jpeg_and_png_detect_content_dimensions_and_exact_raster() -> None:
    source = Image.new("RGB", (18, 12), (20, 100, 220))
    jpeg = decode(encoded(source, "JPEG"))
    png = decode(encoded(source, "PNG"))
    assert jpeg.media_type is SourceMediaType.JPEG
    assert png.media_type is SourceMediaType.PNG
    for result in (jpeg, png):
        assert (result.width, result.height) == (18, 12)
        assert result.exif_orientation is None
        assert (result.grayscale_width, result.grayscale_height) == (9, 8)
        assert isinstance(result.grayscale_pixels, bytes)
        assert len(result.grayscale_pixels) == 72


def test_synthetic_heif_fixture_decodes_primary_frame() -> None:
    result = decode(FIXTURE.read_bytes())
    assert result.media_type is SourceMediaType.HEIF
    assert (result.width, result.height) == (32, 24)
    assert result.exif_orientation is None
    assert len(result.grayscale_pixels) == 72


@pytest.mark.parametrize("orientation", range(1, 9))
def test_exif_orientations_1_through_8_are_retained_and_applied(orientation: int) -> None:
    source = Image.new("RGB", (18, 12), "white")
    for x in range(18):
        for y in range(12):
            source.putpixel((x, y), (x * 12, y * 18, (x + y) * 6))
    content = encoded(source, "JPEG", orientation=orientation)
    result = decode(content)
    with Image.open(io.BytesIO(content)) as reopened:
        expected = (
            ImageOps.exif_transpose(reopened)
            .convert("RGB")
            .convert("L")
            .resize((9, 8), Image.Resampling.LANCZOS)
            .tobytes()
        )
    assert result.exif_orientation == orientation
    assert result.grayscale_pixels == expected


@pytest.mark.parametrize("orientation", [0, 9])
def test_invalid_orientation_is_discarded(orientation: object) -> None:
    result = decode(encoded(Image.new("RGB", (9, 8)), "JPEG", orientation=orientation))
    assert result.exif_orientation is None


def test_alpha_is_composited_over_opaque_white_before_grayscale() -> None:
    source = Image.new("RGBA", (9, 8), (0, 0, 0, 0))
    source.putpixel((0, 0), (0, 0, 0, 255))
    result = decode(encoded(source, "PNG"))
    assert result.grayscale_pixels[0] == 0
    assert set(result.grayscale_pixels[1:]) == {255}


def test_grayscale_source_is_converted_to_canonical_8_bit_l_mode() -> None:
    source = Image.new("L", (9, 8))
    source.putdata(range(72))
    result = decode(encoded(source, "PNG"))
    assert result.grayscale_pixels == bytes(range(72))


def test_larger_image_uses_exact_lanczos_resize(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[tuple[int, int], object]] = []
    original = Image.Image.resize

    def recording_resize(
        self: Image.Image,
        size: tuple[int, int],
        resample: object = None,
        box: object = None,
        reducing_gap: object = None,
    ) -> Image.Image:
        seen.append((size, resample))
        return original(self, size, resample, box, reducing_gap)

    monkeypatch.setattr(Image.Image, "resize", recording_resize)
    result = decode(encoded(Image.new("RGB", (31, 19), (30, 60, 90)), "PNG"))
    assert len(result.grayscale_pixels) == 72
    assert seen[-1] == ((9, 8), Image.Resampling.LANCZOS)


@pytest.mark.parametrize("content", [b"", b"not an image", b"\xff\xd8truncated"])
def test_corrupt_data_is_controlled_decode_failure(content: bytes) -> None:
    with pytest.raises(MediaDecodeError) as caught:
        decode(content)
    assert caught.value.code is SourceImportErrorCode.DECODE_FAILED
    assert caught.value.__cause__ is None
    assert str(caught.value) == SourceImportErrorCode.DECODE_FAILED.value


@pytest.mark.parametrize("format_name", ["BMP", "GIF"])
def test_decodable_but_unsupported_image_format(format_name: str) -> None:
    with pytest.raises(MediaDecodeError) as caught:
        decode(encoded(Image.new("RGB", (9, 8)), format_name))
    assert caught.value.code is SourceImportErrorCode.UNSUPPORTED_FORMAT
    assert caught.value.__cause__ is None


def test_decompression_bomb_warning_and_error_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = encoded(Image.new("RGB", (20, 20)), "PNG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 300)
    with pytest.raises(MediaDecodeError) as warning_failure:
        decode(content)
    assert warning_failure.value.code is SourceImportErrorCode.DECODE_FAILED
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(MediaDecodeError) as error_failure:
        decode(content)
    assert error_failure.value.code is SourceImportErrorCode.DECODE_FAILED


@pytest.mark.parametrize("method", ["convert", "resize", "tobytes"])
def test_conversion_resize_and_tobytes_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    def fail(*_args: object, **_kwargs: object) -> Any:
        raise RuntimeError("unsafe third-party detail")

    monkeypatch.setattr(Image.Image, method, fail)
    with pytest.raises(MediaDecodeError) as caught:
        decode(encoded(Image.new("RGB", (18, 12)), "PNG"))
    assert caught.value.code is SourceImportErrorCode.DECODE_FAILED
    assert caught.value.__cause__ is None
    assert "unsafe" not in str(caught.value)


def test_unavailable_pillow_is_controlled(monkeypatch: pytest.MonkeyPatch) -> None:
    original = media_decoder.importlib.import_module

    def missing(name: str) -> Any:
        if name.startswith("PIL."):
            raise ImportError("unsafe missing pillow detail")
        return original(name)

    monkeypatch.setattr(media_decoder.importlib, "import_module", missing)
    with pytest.raises(MediaDecodeError) as caught:
        decode(b"any")
    assert caught.value.code is SourceImportErrorCode.DECODE_FAILED
    assert caught.value.__cause__ is None


def test_unavailable_pi_heif_is_controlled(monkeypatch: pytest.MonkeyPatch) -> None:
    original = media_decoder.importlib.import_module

    def missing(name: str) -> Any:
        if name == "pi_heif":
            raise ImportError("unsafe missing codec detail")
        return original(name)

    monkeypatch.setattr(media_decoder.importlib, "import_module", missing)
    content = encoded(Image.new("RGB", (9, 8)), "PNG")
    with pytest.raises(MediaDecodeError) as caught:
        decode(content)
    assert caught.value.code is SourceImportErrorCode.DECODE_FAILED
    assert caught.value.__cause__ is None


def test_decoder_does_not_emit_decompression_warning() -> None:
    content = encoded(Image.new("RGB", (20, 20)), "PNG")
    with warnings.catch_warnings(record=True) as caught:
        decode(content)
    assert caught == []
