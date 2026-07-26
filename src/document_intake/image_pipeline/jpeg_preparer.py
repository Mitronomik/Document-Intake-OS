"""Deterministic, metadata-free Pillow JPEG preparation."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO

from PIL import Image, JpegImagePlugin

from document_intake.application.ports.jpeg_preparation import (
    EncodedPreparedJpeg,
    UncompressedRgbRaster,
)
from document_intake.domain.prepared_jpeg import (
    JPEG_QUALITY_SEQUENCE,
    JPEG_RESIZE_PERCENT_SEQUENCE,
    MAX_PREPARED_JPEG_BYTES,
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    PreparedJpegError,
    PreparedJpegErrorCode,
    PreparedJpegPipelineVersion,
)
from document_intake.domain.value_objects import Sha256Digest


def _scaled_dimension(source: int, percent: int) -> int:
    return max(1, (source * percent + 50) // 100)


def _validate_candidate(data: bytes, dimensions: tuple[int, int]) -> None:
    try:
        with Image.open(BytesIO(data)) as decoded:
            decoded.load()
            valid = (
                decoded.format == "JPEG"
                and decoded.mode == "RGB"
                and decoded.size == dimensions
                and not decoded.getexif()
                and "icc_profile" not in decoded.info
                and not decoded.info.get("progressive")
                and not decoded.info.get("progression")
                and JpegImagePlugin.get_sampling(decoded) == 0
                and not ({"xmp", "XML:com.adobe.xmp", "iptc", "comment"} & decoded.info.keys())
            )
            if not valid:
                raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED)
    except PreparedJpegError:
        raise
    except Exception:
        raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED) from None


class PillowPreparedJpegEncoder:
    def encode_prepared_jpeg(
        self, raster: UncompressedRgbRaster, *, pipeline: PreparedJpegPipelineVersion
    ) -> EncodedPreparedJpeg:
        if not isinstance(pipeline, PreparedJpegPipelineVersion):
            raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED)
        try:
            original = Image.frombytes("RGB", (raster.width, raster.height), raster.rgb_pixels)
        except Exception:
            raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED) from None
        source_short = min(original.size)
        seen: set[tuple[int, int]] = set()
        for percent in JPEG_RESIZE_PERCENT_SEQUENCE:
            dimensions = (
                _scaled_dimension(raster.width, percent),
                _scaled_dimension(raster.height, percent),
            )
            if dimensions in seen:
                continue
            seen.add(dimensions)
            if percent < 100 and source_short < 1200:
                continue
            if source_short >= 1200 and min(dimensions) < 1200:
                continue
            try:
                scaled = (
                    original
                    if dimensions == original.size
                    else original.resize(dimensions, Image.Resampling.LANCZOS)
                )
            except Exception:
                raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED) from None
            for quality in JPEG_QUALITY_SEQUENCE:
                output = BytesIO()
                try:
                    scaled.save(
                        output,
                        format="JPEG",
                        quality=quality,
                        progressive=False,
                        optimize=True,
                        subsampling=0,
                    )
                except Exception:
                    raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED) from None
                candidate = output.getvalue()
                _validate_candidate(candidate, dimensions)
                if len(candidate) > MAX_PREPARED_JPEG_BYTES:
                    continue
                return EncodedPreparedJpeg(
                    candidate,
                    dimensions[0],
                    dimensions[1],
                    len(candidate),
                    Sha256Digest(sha256(candidate).hexdigest()),
                    quality,
                    percent,
                    pipeline.pipeline_id,
                    pipeline.version,
                    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
                    PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
                )
        raise PreparedJpegError(PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE)
