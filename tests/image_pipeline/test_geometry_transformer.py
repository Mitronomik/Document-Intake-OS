from document_intake.application.ports.media import DecodedGeometryMedia
from document_intake.domain.enums import SourceMediaType
from document_intake.domain.image_geometry import (
    GeometryPipelineVersion,
    GeometryPoint,
    GeometryQuarterTurn,
    SourceQuadrilateral,
)
from document_intake.image_pipeline.geometry_transformer import PillowGeometryTransformer


def media():
    data = bytes([255, 0, 0]) * 16
    return DecodedGeometryMedia(SourceMediaType.PNG, 4, 4, None, 4, 4, data)


def test_full_frame_and_rotation_deterministic():
    q = SourceQuadrilateral(
        GeometryPoint(0, 0), GeometryPoint(4, 0), GeometryPoint(4, 4), GeometryPoint(0, 4)
    )
    r = PillowGeometryTransformer()
    p = GeometryPipelineVersion("PILLOW_QUAD_BICUBIC", 1)
    a = r.render_geometry(
        media=media(), quadrilateral=q, quarter_turn=GeometryQuarterTurn.DEG_0, pipeline=p
    )
    b = r.render_geometry(
        media=media(), quadrilateral=q, quarter_turn=GeometryQuarterTurn.DEG_0, pipeline=p
    )
    assert a.rgb_pixels == b.rgb_pixels and (a.width, a.height) == (4, 4)
