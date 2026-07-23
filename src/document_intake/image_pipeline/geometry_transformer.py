"""Deterministic Pillow geometry transformer for PR-010."""

from __future__ import annotations

import importlib
from typing import Any

from document_intake.application.ports.media import DecodedGeometryMedia, RenderedGeometryRaster
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryPipelineVersion,
    GeometryQuarterTurn,
    SourceQuadrilateral,
    derive_geometry_dimensions,
)


def _pillow() -> Any:
    return importlib.import_module("PIL.Image")


class PillowGeometryTransformer:
    def render_geometry(
        self,
        *,
        media: DecodedGeometryMedia,
        quadrilateral: SourceQuadrilateral,
        quarter_turn: GeometryQuarterTurn,
        pipeline: GeometryPipelineVersion,
    ) -> RenderedGeometryRaster:
        if (
            not isinstance(media, DecodedGeometryMedia)
            or not isinstance(quadrilateral, SourceQuadrilateral)
            or not isinstance(quarter_turn, GeometryQuarterTurn)
            or not isinstance(pipeline, GeometryPipelineVersion)
        ):
            raise InvalidValueError("geometry_renderer: invalid_type")
        quadrilateral.validate_for_source(media.effective_width, media.effective_height)
        pre_width, pre_height = derive_geometry_dimensions(quadrilateral, GeometryQuarterTurn.DEG_0)
        image_module = _pillow()
        source = image_module.frombytes(
            "RGB", (media.effective_width, media.effective_height), media.rgb_pixels
        )
        q = quadrilateral
        quad_data = (
            q.top_left.x,
            q.top_left.y,
            q.bottom_left.x,
            q.bottom_left.y,
            q.bottom_right.x,
            q.bottom_right.y,
            q.top_right.x,
            q.top_right.y,
        )
        rendered = source.transform(
            (pre_width, pre_height),
            image_module.Transform.QUAD,
            quad_data,
            image_module.Resampling.BICUBIC,
            fill=1,
            fillcolor=(255, 255, 255),
        )
        if quarter_turn is GeometryQuarterTurn.DEG_90:
            rendered = rendered.transpose(image_module.Transpose.ROTATE_270)
        elif quarter_turn is GeometryQuarterTurn.DEG_180:
            rendered = rendered.transpose(image_module.Transpose.ROTATE_180)
        elif quarter_turn is GeometryQuarterTurn.DEG_270:
            rendered = rendered.transpose(image_module.Transpose.ROTATE_90)
        elif quarter_turn is not GeometryQuarterTurn.DEG_0:
            raise InvalidValueError("geometry_renderer.quarter_turn: invalid_value")
        return RenderedGeometryRaster(
            rendered.width, rendered.height, rendered.convert("RGB").tobytes(), pipeline
        )
