"""Deterministic Pillow adapter for composing exactly two RGB rasters."""

from __future__ import annotations

from typing import NoReturn

from PIL import Image

from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.domain.document_side_composition import (
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
    DocumentSideCompositionPipelineVersion,
)
from document_intake.domain.enums import DocumentSideCompositionLayout


def _fail() -> NoReturn:
    raise DocumentSideCompositionError(
        DocumentSideCompositionErrorCode.COMPOSITION_RENDER_FAILED
    ) from None


def _half_up(numerator: int, denominator: int) -> int:
    value = (2 * numerator + denominator) // (2 * denominator)
    if value < 1:
        _fail()
    return value


def _image(raster: UncompressedRgbRaster) -> Image.Image:
    try:
        return Image.frombytes("RGB", (raster.width, raster.height), raster.rgb_pixels)
    except Exception:
        _fail()


def _resize(image: Image.Image, dimensions: tuple[int, int]) -> Image.Image:
    if image.size == dimensions:
        return image.copy()
    try:
        return image.resize(dimensions, Image.Resampling.BICUBIC)
    except Exception:
        _fail()


class PillowDocumentSideComposer:
    def compose(
        self,
        *,
        side_1: UncompressedRgbRaster,
        side_2: UncompressedRgbRaster,
        layout: DocumentSideCompositionLayout,
        outer_margin_px: int,
        inter_side_gap_px: int,
        pipeline: DocumentSideCompositionPipelineVersion,
    ) -> UncompressedRgbRaster:
        if (
            not isinstance(side_1, UncompressedRgbRaster)
            or not isinstance(side_2, UncompressedRgbRaster)
            or not isinstance(pipeline, DocumentSideCompositionPipelineVersion)
            or type(outer_margin_px) is not int
            or not 0 <= outer_margin_px <= 256
            or type(inter_side_gap_px) is not int
            or not 0 <= inter_side_gap_px <= 256
        ):
            _fail()
        if layout is DocumentSideCompositionLayout.VERTICAL:
            return self._vertical(side_1, side_2, outer_margin_px, inter_side_gap_px)
        if layout is DocumentSideCompositionLayout.HORIZONTAL:
            return self._horizontal(side_1, side_2, outer_margin_px, inter_side_gap_px)
        _fail()

    def _vertical(
        self, side_1: UncompressedRgbRaster, side_2: UncompressedRgbRaster, margin: int, gap: int
    ) -> UncompressedRgbRaster:
        target_width = min(side_1.width, side_2.width)
        height_1 = (
            side_1.height
            if side_1.width == target_width
            else _half_up(side_1.height * target_width, side_1.width)
        )
        height_2 = (
            side_2.height
            if side_2.width == target_width
            else _half_up(side_2.height * target_width, side_2.width)
        )
        first = _resize(_image(side_1), (target_width, height_1))
        second = _resize(_image(side_2), (target_width, height_2))
        canvas = Image.new(
            "RGB", (target_width + 2 * margin, height_1 + height_2 + gap + 2 * margin), "white"
        )
        canvas.paste(first, (margin, margin))
        canvas.paste(second, (margin, margin + height_1 + gap))
        return UncompressedRgbRaster(canvas.width, canvas.height, canvas.tobytes())

    def _horizontal(
        self, side_1: UncompressedRgbRaster, side_2: UncompressedRgbRaster, margin: int, gap: int
    ) -> UncompressedRgbRaster:
        target_height = min(side_1.height, side_2.height)
        width_1 = (
            side_1.width
            if side_1.height == target_height
            else _half_up(side_1.width * target_height, side_1.height)
        )
        width_2 = (
            side_2.width
            if side_2.height == target_height
            else _half_up(side_2.width * target_height, side_2.height)
        )
        first = _resize(_image(side_1), (width_1, target_height))
        second = _resize(_image(side_2), (width_2, target_height))
        canvas = Image.new(
            "RGB", (width_1 + width_2 + gap + 2 * margin, target_height + 2 * margin), "white"
        )
        canvas.paste(first, (margin, margin))
        canvas.paste(second, (margin + width_1 + gap, margin))
        return UncompressedRgbRaster(canvas.width, canvas.height, canvas.tobytes())
