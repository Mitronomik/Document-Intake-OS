"""Ephemeral media preflight for document-region confirmation."""

from __future__ import annotations

from collections.abc import Callable

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.media import (
    DecodedGeometryMedia,
    GeometryDecoderPort,
    GeometryRendererPort,
    RenderedGeometryRaster,
)
from document_intake.application.ports.storage import StoragePort
from document_intake.application.services.document_region_persistence import (
    map_geometry_validation_error,
)
from document_intake.application.services.image_geometry import ImageGeometryError
from document_intake.domain.entities import SourceFile
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_geometry import (
    GeometryErrorCode,
    GeometryQuarterTurn,
    ImageGeometryRecipe,
    SourceQuadrilateral,
)

DimensionDeriver = Callable[[SourceQuadrilateral, GeometryQuarterTurn], tuple[int, int]]


def render_selected_set(
    source: SourceFile,
    stored: StoredArtifactRecord,
    selected: tuple[ImageGeometryRecipe, ...],
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    storage: StoragePort,
    derive_dimensions: DimensionDeriver,
) -> None:
    content = _read_source_bytes(stored, storage)
    media = _decode_source(content, decoder)
    _verify_effective_dimensions(source, media)
    _validate_selected_geometry(selected, media)
    dimensions = _derive_output_dimensions(selected, derive_dimensions)
    tuple(
        _render_recipe(recipe, media, renderer, expected)
        for recipe, expected in zip(selected, dimensions, strict=True)
    )


def _read_source_bytes(stored: StoredArtifactRecord, storage: StoragePort) -> bytes:
    try:
        return storage.read_bytes(expected=stored)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.ARTIFACT_INTEGRITY_FAILED) from None


def _decode_source(content: bytes, decoder: GeometryDecoderPort) -> DecodedGeometryMedia:
    try:
        return decoder.decode_for_geometry(content=content)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.DECODE_FAILED) from None


def _verify_effective_dimensions(source: SourceFile, media: DecodedGeometryMedia) -> None:
    expected = (
        (source.height, source.width)
        if source.exif_orientation in {5, 6, 7, 8}
        else (source.width, source.height)
    )
    if (media.effective_width, media.effective_height) != expected:
        raise ImageGeometryError(GeometryErrorCode.SOURCE_DIMENSIONS_MISMATCH)


def _validate_selected_geometry(
    selected: tuple[ImageGeometryRecipe, ...], media: DecodedGeometryMedia
) -> None:
    try:
        for recipe in selected:
            recipe.quadrilateral.validate_for_source(media.effective_width, media.effective_height)
    except InvalidValueError as error:
        map_geometry_validation_error(error)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None


def _derive_output_dimensions(
    selected: tuple[ImageGeometryRecipe, ...], derive_dimensions: DimensionDeriver
) -> tuple[tuple[int, int], ...]:
    try:
        return tuple(
            derive_dimensions(recipe.quadrilateral, recipe.quarter_turn) for recipe in selected
        )
    except InvalidValueError as error:
        map_geometry_validation_error(error)
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None


def _render_recipe(
    recipe: ImageGeometryRecipe,
    media: DecodedGeometryMedia,
    renderer: GeometryRendererPort,
    expected: tuple[int, int],
) -> RenderedGeometryRaster:
    try:
        rendered = renderer.render_geometry(
            media=media,
            quadrilateral=recipe.quadrilateral,
            quarter_turn=recipe.quarter_turn,
            pipeline=recipe.pipeline,
        )
        if (
            (rendered.width, rendered.height) != expected
            or rendered.pipeline != recipe.pipeline
            or len(rendered.rgb_pixels) != rendered.width * rendered.height * 3
        ):
            raise ValueError
        return rendered
    except Exception:
        raise ImageGeometryError(GeometryErrorCode.RENDER_FAILED) from None
