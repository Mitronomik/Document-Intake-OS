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


@dataclass(frozen=True, slots=True)
class DecodedQualityMedia:
    media_type: SourceMediaType
    encoded_width: int
    encoded_height: int
    exif_orientation: int | None
    effective_width: int
    effective_height: int
    grayscale_pixels: bytes
    grayscale_width: int
    grayscale_height: int


class QualityAnalysisDecoderPort(Protocol):
    def decode_for_quality(self, *, content: bytes) -> DecodedQualityMedia: ...


class MediaDecoderPort(Protocol):
    def decode_for_import(self, *, content: bytes) -> DecodedMedia: ...
