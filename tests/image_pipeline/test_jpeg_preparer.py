from PIL import Image, JpegImagePlugin

from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.domain.prepared_jpeg import (
    MAX_PREPARED_JPEG_BYTES,
    PreparedJpegPipelineVersion,
)
from document_intake.image_pipeline.jpeg_preparer import (
    PillowPreparedJpegEncoder,
    _scaled_dimension,
)


def test_preparer_is_deterministic_metadata_free_rgb_jpeg() -> None:
    pixels = bytes(
        (x * 17 + y * 31 + channel * 53) % 256
        for y in range(64)
        for x in range(96)
        for channel in range(3)
    )
    raster = UncompressedRgbRaster(96, 64, pixels)
    encoder = PillowPreparedJpegEncoder()
    first = encoder.encode_prepared_jpeg(raster, pipeline=PreparedJpegPipelineVersion())
    second = encoder.encode_prepared_jpeg(raster, pipeline=PreparedJpegPipelineVersion())
    assert first == second
    assert first.byte_size <= MAX_PREPARED_JPEG_BYTES
    assert first.jpeg_quality == 95
    assert first.resize_percent == 100
    assert JpegImagePlugin.get_sampling(Image.open(__import__("io").BytesIO(first.jpeg_bytes))) == 0


def test_half_up_dimension_math() -> None:
    assert _scaled_dimension(5, 50) == 3


def test_raster_rejects_invalid_dimensions_and_lengths() -> None:
    import pytest

    from document_intake.domain.errors import InvalidValueError

    for args in ((0, 1, b""), (True, 1, b"\0\0\0"), (1, 0, b""), (1, 1, b"bad"[:2])):
        with pytest.raises(InvalidValueError):
            UncompressedRgbRaster(*args)  # type: ignore[arg-type]


def test_structural_decode_failure_is_encoding_failed_without_chaining() -> None:
    import pytest

    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline.jpeg_preparer import _validate_candidate

    with pytest.raises(PreparedJpegError) as exc:
        _validate_candidate(b"not-jpeg", (1, 1))
    assert exc.value.code is PreparedJpegErrorCode.JPEG_ENCODING_FAILED
    assert exc.value.__cause__ is None


def test_encoded_result_rejects_inconsistent_metadata() -> None:
    from hashlib import sha256

    import pytest

    from document_intake.application.ports.jpeg_preparation import EncodedPreparedJpeg
    from document_intake.domain.errors import InvalidValueError
    from document_intake.domain.prepared_jpeg import (
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        PREPARED_JPEG_PIPELINE_ID,
    )
    from document_intake.domain.value_objects import Sha256Digest

    data = b"synthetic"
    digest = Sha256Digest(sha256(data).hexdigest())
    with pytest.raises(InvalidValueError):
        EncodedPreparedJpeg(
            data,
            1,
            1,
            len(data) + 1,
            digest,
            95,
            100,
            PREPARED_JPEG_PIPELINE_ID,
            1,
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            1,
        )
    with pytest.raises(InvalidValueError):
        EncodedPreparedJpeg(
            data,
            1,
            1,
            len(data),
            digest,
            59,
            100,
            PREPARED_JPEG_PIPELINE_ID,
            1,
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            1,
        )


def test_candidate_plan_is_exact_quality_before_scale_and_guarded() -> None:
    from document_intake.image_pipeline.jpeg_preparer import _iter_candidate_attempts

    large = UncompressedRgbRaster(2400, 2400, b"\0" * (2400 * 2400 * 3))
    plan = _iter_candidate_attempts(large)
    assert [(a.resize_percent, a.jpeg_quality) for a in plan] == [
        (scale, quality)
        for scale in (100, 90, 80, 70, 60, 50)
        for quality in (95, 90, 85, 80, 75, 70, 65, 60)
    ]
    assert [(a.width, a.height) for a in plan[::8]] == [
        (2400, 2400),
        (2160, 2160),
        (1920, 1920),
        (1680, 1680),
        (1440, 1440),
        (1200, 1200),
    ]
    small = UncompressedRgbRaster(5, 5, b"\0" * 75)
    assert {a.resize_percent for a in _iter_candidate_attempts(small)} == {100}


def test_attempt_observer_matches_selected_first_candidate() -> None:
    from document_intake.image_pipeline.jpeg_preparer import (
        _encode_prepared_jpeg_internal,
        _iter_candidate_attempts,
    )

    raster = UncompressedRgbRaster(96, 64, b"\0" * (96 * 64 * 3))
    observed = []
    result = _encode_prepared_jpeg_internal(
        raster, pipeline=PreparedJpegPipelineVersion(), attempt_observer=observed.append
    )
    assert observed == list(_iter_candidate_attempts(raster)[:1])
    assert (result.resize_percent, result.jpeg_quality, result.width, result.height) == (
        observed[-1].resize_percent,
        observed[-1].jpeg_quality,
        observed[-1].width,
        observed[-1].height,
    )
