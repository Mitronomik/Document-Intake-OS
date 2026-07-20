"""Media decoder application port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from document_intake.domain.enums import SourceMediaType


@dataclass(frozen=True, slots=True)
class DecodedMedia:
    media_type: SourceMediaType
    width: int
    height: int
    exif_orientation: int | None
    grayscale_pixels: bytes
    grayscale_width: int
    grayscale_height: int


class MediaDecoderPort(Protocol):
    def decode_for_import(self, *, content: bytes) -> DecodedMedia: ...
