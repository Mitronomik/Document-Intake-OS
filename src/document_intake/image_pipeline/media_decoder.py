"""Pillow/pi-heif media decoder and DHASH64 implementation for PR-008."""

from __future__ import annotations

import io
import warnings

import pi_heif
from PIL import Image, ImageOps

from document_intake.application.ports.media import DecodedMedia
from document_intake.domain.enums import SourceImportErrorCode, SourceMediaType

_HEIF_REGISTERED = False


class MediaDecodeError(Exception):
    def __init__(self, code: SourceImportErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


def _register_heif() -> None:
    global _HEIF_REGISTERED
    if not _HEIF_REGISTERED:
        pi_heif.register_heif_opener()
        _HEIF_REGISTERED = True


def _media_type(fmt: str | None) -> SourceMediaType:
    match (fmt or "").upper():
        case "JPEG":
            return SourceMediaType.JPEG
        case "PNG":
            return SourceMediaType.PNG
        case "HEIF" | "HEIC":
            return SourceMediaType.HEIF
        case _:
            raise MediaDecodeError(SourceImportErrorCode.UNSUPPORTED_FORMAT)


class PillowMediaDecoder:
    def __init__(self) -> None:
        _register_heif()

    def decode_for_import(self, *, content: bytes) -> DecodedMedia:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    image.seek(0)
                    media_type = _media_type(image.format)
                    width, height = image.size
                    orientation_obj = image.getexif().get(274)
                    orientation = orientation_obj if type(orientation_obj) is int and 1 <= orientation_obj <= 8 else None
                    working = ImageOps.exif_transpose(image.copy())
                    working.load()
        except MediaDecodeError:
            raise
        except Exception as exc:
            raise MediaDecodeError(SourceImportErrorCode.DECODE_FAILED) from exc
        if "A" in working.getbands() or working.mode in {"RGBA", "LA", "PA"} or "transparency" in working.info:
            rgba = working.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            bg.alpha_composite(rgba)
            rgb = bg.convert("RGB")
        else:
            rgb = working.convert("RGB")
        gray = rgb.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = gray.tobytes()
        if len(pixels) != 72:
            raise MediaDecodeError(SourceImportErrorCode.DECODE_FAILED)
        return DecodedMedia(media_type, width, height, orientation, pixels, 9, 8)


def dhash64(grayscale_pixels: bytes, grayscale_width: int = 9, grayscale_height: int = 8) -> str:
    if grayscale_width != 9 or grayscale_height != 8 or len(grayscale_pixels) != 72:
        raise ValueError("ERR_IMPORT_DECODED_RASTER_INVALID")
    bits = 0
    for row in range(8):
        offset = row * 9
        for col in range(8):
            bits = (bits << 1) | (1 if grayscale_pixels[offset + col] > grayscale_pixels[offset + col + 1] else 0)
    return f"{bits:016x}"


def dhash64_hamming_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()
