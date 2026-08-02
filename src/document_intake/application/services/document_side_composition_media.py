"""Original-byte replay, pure composition, and final JPEG encoding."""

from __future__ import annotations

from document_intake.application.ports.document_side_composition import DocumentSideComposerPort
from document_intake.application.ports.jpeg_preparation import (
    EncodedPreparedJpeg,
    PreparedJpegEncoderPort,
    UncompressedRgbRaster,
)
from document_intake.application.ports.media import GeometryDecoderPort, GeometryRendererPort
from document_intake.application.ports.storage import StoragePort
from document_intake.application.services.document_side_composition_loading import (
    DocumentSideContext,
)
from document_intake.application.services.document_side_composition_validation import fail
from document_intake.domain.document_side_composition import (
    DocumentSideCompositionError,
    DocumentSideCompositionErrorCode,
    DocumentSideCompositionPipelineVersion,
)
from document_intake.domain.enums import DocumentSideCompositionLayout
from document_intake.domain.image_geometry import derive_geometry_dimensions
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    PREPARED_JPEG_PIPELINE_ID,
    PREPARED_JPEG_PIPELINE_VERSION,
    PreparedJpegError,
    PreparedJpegErrorCode,
    PreparedJpegPipelineVersion,
)


def render_document_side(
    context: DocumentSideContext,
    *,
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    storage: StoragePort,
) -> UncompressedRgbRaster:
    try:
        content = storage.read_bytes(expected=context.original)
    except Exception:
        fail(DocumentSideCompositionErrorCode.ORIGINAL_BYTES_INVALID)
    try:
        media = decoder.decode_for_geometry(content=content)
    except Exception:
        fail(DocumentSideCompositionErrorCode.ORIGINAL_BYTES_INVALID)
    source_dimensions = (
        (context.source.height, context.source.width)
        if context.source.exif_orientation in {5, 6, 7, 8}
        else (context.source.width, context.source.height)
    )
    if (
        media.effective_width,
        media.effective_height,
    ) != source_dimensions or source_dimensions != (
        context.recipe.source_effective_width,
        context.recipe.source_effective_height,
    ):
        fail(DocumentSideCompositionErrorCode.SOURCE_DIMENSIONS_MISMATCH)
    try:
        rendered = renderer.render_geometry(
            media=media,
            quadrilateral=context.recipe.quadrilateral,
            quarter_turn=context.recipe.quarter_turn,
            pipeline=context.recipe.pipeline,
        )
        expected = derive_geometry_dimensions(
            context.recipe.quadrilateral, context.recipe.quarter_turn
        )
        if (
            (rendered.width, rendered.height) != expected
            or rendered.pipeline != context.recipe.pipeline
            or len(rendered.rgb_pixels) != rendered.width * rendered.height * 3
        ):
            fail(DocumentSideCompositionErrorCode.GEOMETRY_RENDER_FAILED)
        return UncompressedRgbRaster(rendered.width, rendered.height, rendered.rgb_pixels)
    except DocumentSideCompositionError:
        raise
    except Exception:
        fail(DocumentSideCompositionErrorCode.GEOMETRY_RENDER_FAILED)


def compose_and_encode(
    side_1: UncompressedRgbRaster,
    side_2: UncompressedRgbRaster,
    *,
    layout: DocumentSideCompositionLayout,
    outer_margin_px: int,
    inter_side_gap_px: int,
    composer: DocumentSideComposerPort,
    encoder: PreparedJpegEncoderPort,
) -> EncodedPreparedJpeg:
    try:
        composed = composer.compose(
            side_1=side_1,
            side_2=side_2,
            layout=layout,
            outer_margin_px=outer_margin_px,
            inter_side_gap_px=inter_side_gap_px,
            pipeline=DocumentSideCompositionPipelineVersion(),
        )
        if not isinstance(composed, UncompressedRgbRaster):
            fail(DocumentSideCompositionErrorCode.COMPOSITION_RENDER_FAILED)
    except DocumentSideCompositionError:
        raise
    except Exception:
        fail(DocumentSideCompositionErrorCode.COMPOSITION_RENDER_FAILED)
    try:
        encoded = encoder.encode_prepared_jpeg(
            composed,
            pipeline=PreparedJpegPipelineVersion(),
        )
    except PreparedJpegError as error:
        code = (
            DocumentSideCompositionErrorCode.SIZE_LIMIT_UNREACHABLE
            if error.code is PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE
            else DocumentSideCompositionErrorCode.JPEG_ENCODING_FAILED
        )
        fail(code)
    except Exception:
        fail(DocumentSideCompositionErrorCode.JPEG_ENCODING_FAILED)
    if not isinstance(encoded, EncodedPreparedJpeg) or (
        encoded.pipeline_id,
        encoded.pipeline_version,
        encoded.output_contract_id,
        encoded.output_contract_version,
    ) != (
        PREPARED_JPEG_PIPELINE_ID,
        PREPARED_JPEG_PIPELINE_VERSION,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    ):
        fail(DocumentSideCompositionErrorCode.JPEG_ENCODING_FAILED)
    return encoded
