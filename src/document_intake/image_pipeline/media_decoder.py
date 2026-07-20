"""Pillow/pi-heif media decoder and DHASH64 implementation for PR-008."""

from __future__ import annotations

import importlib
import io
import warnings
from typing import Any

from document_intake.application.ports.media import DecodedMedia
from document_intake.domain.enums import SourceImportErrorCode, SourceMediaType

_HEIF_REGISTERED = False


class MediaDecodeError(Exception):
    """Controlled PII-safe media decode failure."""

    def __init__(self, code: SourceImportErrorCode) -> None:
        self.code = code
        super().__init__(code.value)

    def __repr__(self) -> str:
        return f"MediaDecodeError(code={self.code.value})"


def _import_pillow() -> tuple[Any, Any]:
    try:
        image_module = importlib.import_module("PIL.Image")
        image_ops_module = importlib.import_module("PIL.ImageOps")
    except Exception:
        raise MediaDecodeError(SourceImportErrorCode.DECODE_FAILED) from None
    return image_module, image_ops_module


def _register_heif_opener() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    try:
        pi_heif = importlib.import_module("pi_heif")
        pi_heif.register_heif_opener()
    except Exception:
        raise MediaDecodeError(SourceImportErrorCode.DECODE_FAILED) from None
    _HEIF_REGISTERED = True


def _media_type(format_name: str | None) -> SourceMediaType:
    match (format_name or "").upper():
        case "JPEG":
            return SourceMediaType.JPEG
        case "PNG":
            return SourceMediaType.PNG
        case "HEIF" | "HEIC":
            return SourceMediaType.HEIF
        case _:
            raise MediaDecodeError(SourceImportErrorCode.UNSUPPORTED_FORMAT)


def _orientation(value: object) -> int | None:
    if type(value) is int and 1 <= value <= 8:
        return value
    return None


class PillowMediaDecoder:
    def decode_for_import(self, *, content: bytes) -> DecodedMedia:
        try:
            image_module, image_ops_module = _import_pillow()
            _register_heif_opener()
            with warnings.catch_warnings():
                warnings.simplefilter("error", image_module.DecompressionBombWarning)
                with image_module.open(io.BytesIO(content)) as image:
                    image.seek(0)
                    media_type = _media_type(image.format)
                    width, height = image.size
                    exif_orientation = _orientation(image.getexif().get(274))
                    primary = image.copy()
                    primary.load()
                working = image_ops_module.exif_transpose(primary)
                bands = working.getbands()
                has_alpha = "A" in bands or working.mode in {"RGBA", "LA", "PA"}
                has_transparency = "transparency" in working.info
                if has_alpha or has_transparency:
                    rgba = working.convert("RGBA")
                    background = image_module.new("RGBA", rgba.size, (255, 255, 255, 255))
                    background.alpha_composite(rgba)
                    rgb = background.convert("RGB")
                else:
                    rgb = working.convert("RGB")
                grayscale = rgb.convert("L").resize((9, 8), image_module.Resampling.LANCZOS)
                grayscale_pixels = grayscale.tobytes()
                if len(grayscale_pixels) != 72:
                    raise MediaDecodeError(SourceImportErrorCode.DECODE_FAILED)
                return DecodedMedia(
                    media_type=media_type,
                    width=width,
                    height=height,
                    exif_orientation=exif_orientation,
                    grayscale_pixels=grayscale_pixels,
                    grayscale_width=9,
                    grayscale_height=8,
                )
        except MediaDecodeError:
            raise
        except Exception:
            raise MediaDecodeError(SourceImportErrorCode.DECODE_FAILED) from None


def dhash64(grayscale_pixels: bytes, grayscale_width: int = 9, grayscale_height: int = 8) -> str:
    if grayscale_width != 9 or grayscale_height != 8 or len(grayscale_pixels) != 72:
        raise ValueError("ERR_IMPORT_DECODED_RASTER_INVALID")
    bits = 0
    for row in range(8):
        offset = row * 9
        for col in range(8):
            bit = 1 if grayscale_pixels[offset + col] > grayscale_pixels[offset + col + 1] else 0
            bits = (bits << 1) | bit
    return f"{bits:016x}"


def dhash64_hamming_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()
