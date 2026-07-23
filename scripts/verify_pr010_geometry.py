"""Synthetic PR-010 geometry verifier."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from document_intake.application.ports.media import DecodedGeometryMedia
from document_intake.domain.enums import SourceMediaType
from document_intake.domain.image_geometry import (
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    SourceQuadrilateral,
)
from document_intake.image_pipeline.geometry_transformer import PillowGeometryTransformer
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder


def _synthetic_png() -> bytes:
    img = Image.new("RGB", (8, 6), "white")
    px = img.load()
    assert px is not None
    for x in range(8):
        px[x, 0] = (255, 0, 0)
        px[x, 5] = (0, 0, 255)
    for y in range(6):
        px[0, y] = (0, 255, 0)
        px[7, y] = (255, 255, 0)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def main() -> int:
    content = _synthetic_png()
    before = bytes(content)
    media = PillowMediaDecoder().decode_for_geometry(content=content)
    if not isinstance(media, DecodedGeometryMedia) or media.media_type is not SourceMediaType.PNG:
        raise SystemExit("ERR_PR010_DECODE")
    q = SourceQuadrilateral(
        GeometryPoint(0, 0),
        GeometryPoint(media.effective_width, 0),
        GeometryPoint(media.effective_width, media.effective_height),
        GeometryPoint(0, media.effective_height),
    )
    renderer = PillowGeometryTransformer()
    pipeline = GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1)
    first = renderer.render_geometry(
        media=media, quadrilateral=q, quarter_turn=GeometryQuarterTurn.DEG_90, pipeline=pipeline
    )
    second = renderer.render_geometry(
        media=media, quadrilateral=q, quarter_turn=GeometryQuarterTurn.DEG_90, pipeline=pipeline
    )
    if first.rgb_pixels != second.rgb_pixels or (first.width, first.height) != (6, 8):
        raise SystemExit("ERR_PR010_DETERMINISM")
    if content != before:
        raise SystemExit("ERR_PR010_ORIGINAL_MUTATED")
    try:
        SourceQuadrilateral(
            GeometryPoint(0, 0), GeometryPoint(1, 0), GeometryPoint(1, 1), GeometryPoint(0, 1)
        ).validate_for_source(8, 6)
    except Exception:
        pass
    else:
        raise SystemExit("ERR_PR010_INVALID_GEOMETRY")
    print(
        "PR-010 geometry verifier passed: synthetic decode/render deterministic; "
        "original unchanged; no prepared JPEG published"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
