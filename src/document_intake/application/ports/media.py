"""Media decoder application port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from document_intake.domain.enums import SourceMediaType
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryPipelineVersion,
    GeometryQuarterTurn,
    SourceQuadrilateral,
)


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

    def __post_init__(self) -> None:
        if not isinstance(self.media_type, SourceMediaType):
            raise InvalidValueError("decoded_quality_media.media_type: invalid_type")
        for name in (
            "encoded_width",
            "encoded_height",
            "effective_width",
            "effective_height",
            "grayscale_width",
            "grayscale_height",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise InvalidValueError(f"decoded_quality_media.{name}: invalid_value")
        if self.exif_orientation is not None and (
            type(self.exif_orientation) is not int or not 1 <= self.exif_orientation <= 8
        ):
            raise InvalidValueError("decoded_quality_media.exif_orientation: invalid_value")
        if self.exif_orientation in {5, 6, 7, 8}:
            expected_dimensions = (self.encoded_height, self.encoded_width)
        else:
            expected_dimensions = (self.encoded_width, self.encoded_height)
        if (self.effective_width, self.effective_height) != expected_dimensions:
            raise InvalidValueError("decoded_quality_media.effective_dimensions: invalid_value")
        if self.grayscale_width != self.effective_width:
            raise InvalidValueError("decoded_quality_media.grayscale_width: mismatch")
        if self.grayscale_height != self.effective_height:
            raise InvalidValueError("decoded_quality_media.grayscale_height: mismatch")
        if type(self.grayscale_pixels) is not bytes:
            raise InvalidValueError("decoded_quality_media.grayscale_pixels: invalid_type")
        if len(self.grayscale_pixels) != self.grayscale_width * self.grayscale_height:
            raise InvalidValueError("decoded_quality_media.grayscale_pixels: invalid_length")


@dataclass(frozen=True, slots=True)
class DecodedGeometryMedia:
    media_type: SourceMediaType
    encoded_width: int
    encoded_height: int
    exif_orientation: int | None
    effective_width: int
    effective_height: int
    rgb_pixels: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.media_type, SourceMediaType):
            raise InvalidValueError("decoded_geometry_media.media_type: invalid_type")
        for name in ("encoded_width", "encoded_height", "effective_width", "effective_height"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise InvalidValueError(f"decoded_geometry_media.{name}: invalid_value")
        if self.exif_orientation is not None and (
            type(self.exif_orientation) is not int or not 1 <= self.exif_orientation <= 8
        ):
            raise InvalidValueError("decoded_geometry_media.exif_orientation: invalid_value")
        expected_dimensions = (
            (self.encoded_height, self.encoded_width)
            if self.exif_orientation in {5, 6, 7, 8}
            else (self.encoded_width, self.encoded_height)
        )
        if (self.effective_width, self.effective_height) != expected_dimensions:
            raise InvalidValueError("decoded_geometry_media.effective_dimensions: invalid_value")
        if (
            type(self.rgb_pixels) is not bytes
            or len(self.rgb_pixels) != self.effective_width * self.effective_height * 3
        ):
            raise InvalidValueError("decoded_geometry_media.rgb_pixels: invalid_length")


@dataclass(frozen=True, slots=True)
class RenderedGeometryRaster:
    width: int
    height: int
    rgb_pixels: bytes
    pipeline: GeometryPipelineVersion

    def __post_init__(self) -> None:
        for name in ("width", "height"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise InvalidValueError(f"rendered_geometry_raster.{name}: invalid_value")
        if (
            type(self.rgb_pixels) is not bytes
            or len(self.rgb_pixels) != self.width * self.height * 3
        ):
            raise InvalidValueError("rendered_geometry_raster.rgb_pixels: invalid_length")
        if not isinstance(self.pipeline, GeometryPipelineVersion):
            raise InvalidValueError("rendered_geometry_raster.pipeline: invalid_type")


class QualityAnalysisDecoderPort(Protocol):
    def decode_for_quality(self, *, content: bytes) -> DecodedQualityMedia: ...


class GeometryDecoderPort(Protocol):
    def decode_for_geometry(self, *, content: bytes) -> DecodedGeometryMedia: ...


class GeometryRendererPort(Protocol):
    def render_geometry(
        self,
        *,
        media: DecodedGeometryMedia,
        quadrilateral: SourceQuadrilateral,
        quarter_turn: GeometryQuarterTurn,
        pipeline: GeometryPipelineVersion,
    ) -> RenderedGeometryRaster: ...


class MediaDecoderPort(Protocol):
    def decode_for_import(self, *, content: bytes) -> DecodedMedia: ...
