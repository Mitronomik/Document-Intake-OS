"""Deterministic, metadata-free Pillow JPEG preparation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class _CandidateAttempt:
    resize_percent: int
    jpeg_quality: int
    width: int
    height: int


def _iter_candidate_attempts(raster: UncompressedRgbRaster) -> tuple[_CandidateAttempt, ...]:
    source_short = min(raster.width, raster.height)
    seen: set[tuple[int, int]] = set()
    attempts: list[_CandidateAttempt] = []
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
        attempts.extend(
            _CandidateAttempt(percent, quality, *dimensions) for quality in JPEG_QUALITY_SEQUENCE
        )
    return tuple(attempts)


def _pillow_candidate_encoder(image: Image.Image, quality: int) -> bytes:
    output = BytesIO()
    image.save(
        output, format="JPEG", quality=quality, progressive=False, optimize=True, subsampling=0
    )
    return output.getvalue()


def _encode_prepared_jpeg_internal(
    raster: UncompressedRgbRaster,
    *,
    pipeline: PreparedJpegPipelineVersion,
    attempt_observer: Callable[[_CandidateAttempt], None] | None = None,
    candidate_encoder: Callable[[Image.Image, int], bytes] | None = None,
) -> EncodedPreparedJpeg:
    if not isinstance(pipeline, PreparedJpegPipelineVersion):
        raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED)
    try:
        original = Image.frombytes("RGB", (raster.width, raster.height), raster.rgb_pixels)
    except Exception:
        raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED) from None
    encode = candidate_encoder or _pillow_candidate_encoder
    scaled_by_dimensions: dict[tuple[int, int], Image.Image] = {}
    for attempt in _iter_candidate_attempts(raster):
        dimensions = (attempt.width, attempt.height)
        try:
            scaled = scaled_by_dimensions.get(dimensions)
            if scaled is None:
                scaled = (
                    original
                    if dimensions == original.size
                    else original.resize(dimensions, Image.Resampling.LANCZOS)
                )
                scaled_by_dimensions[dimensions] = scaled
            if attempt_observer is not None:
                attempt_observer(attempt)
            candidate = encode(scaled, attempt.jpeg_quality)
        except Exception:
            raise PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED) from None
        _validate_candidate(candidate, dimensions)
        if len(candidate) > MAX_PREPARED_JPEG_BYTES:
            continue
        return EncodedPreparedJpeg(
            candidate,
            attempt.width,
            attempt.height,
            len(candidate),
            Sha256Digest(sha256(candidate).hexdigest()),
            attempt.jpeg_quality,
            attempt.resize_percent,
            pipeline.pipeline_id,
            pipeline.version,
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
        )
    raise PreparedJpegError(PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE)


class PillowPreparedJpegEncoder:
    def encode_prepared_jpeg(
        self, raster: UncompressedRgbRaster, *, pipeline: PreparedJpegPipelineVersion
    ) -> EncodedPreparedJpeg:
        return _encode_prepared_jpeg_internal(raster, pipeline=pipeline)
