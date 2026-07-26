from io import BytesIO

import pytest
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


@pytest.mark.parametrize(
    ("width", "height", "expected_scales"),
    [(2401, 2403, (100, 90, 80, 70, 60, 50)), (1200, 1600, (100,)), (1199, 2000, (100,))],
)
def test_candidate_plan_guards_and_half_up_dimensions(
    width: int, height: int, expected_scales: tuple[int, ...]
) -> None:
    from document_intake.image_pipeline.jpeg_preparer import _iter_candidate_attempts

    raster = UncompressedRgbRaster(width, height, b"\0" * (width * height * 3))
    attempts = _iter_candidate_attempts(raster)
    assert tuple(dict.fromkeys(item.resize_percent for item in attempts)) == expected_scales
    assert all(item.jpeg_quality >= 60 and item.resize_percent >= 50 for item in attempts)
    for item in attempts:
        assert item.width == max(1, (width * item.resize_percent + 50) // 100)
        assert item.height == max(1, (height * item.resize_percent + 50) // 100)


def test_duplicate_candidate_dimensions_are_removed() -> None:
    from document_intake.image_pipeline.jpeg_preparer import _iter_candidate_attempts

    raster = UncompressedRgbRaster(1, 1, b"\0\0\0")
    plan = _iter_candidate_attempts(raster)
    assert len(plan) == 8
    assert {(item.width, item.height) for item in plan} == {(1, 1)}


def _jpeg_for(image: Image.Image, quality: int) -> bytes:
    output = BytesIO()
    image.save(output, "JPEG", quality=quality, progressive=False, subsampling=0)
    return output.getvalue()


def test_full_48_attempt_exhaustion_is_observed_in_exact_order() -> None:
    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline.jpeg_preparer import (
        _encode_prepared_jpeg_internal,
        _iter_candidate_attempts,
    )

    raster = UncompressedRgbRaster(2400, 2400, b"\0" * (2400 * 2400 * 3))
    observed = []

    def oversized(image: Image.Image, quality: int) -> bytes:
        data = _jpeg_for(image, quality)
        return data + b"\0" * (MAX_PREPARED_JPEG_BYTES + 1 - len(data))

    with pytest.raises(PreparedJpegError) as exc:
        _encode_prepared_jpeg_internal(
            raster,
            pipeline=PreparedJpegPipelineVersion(),
            attempt_observer=observed.append,
            candidate_encoder=oversized,
        )
    assert exc.value.code is PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE
    assert observed == list(_iter_candidate_attempts(raster))
    assert len(observed) == 48


@pytest.mark.parametrize("fit_size", [MAX_PREPARED_JPEG_BYTES, MAX_PREPARED_JPEG_BYTES + 1])
def test_exact_byte_ceiling_and_ceiling_plus_one(fit_size: int) -> None:
    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline.jpeg_preparer import _encode_prepared_jpeg_internal

    raster = UncompressedRgbRaster(32, 32, b"\0" * (32 * 32 * 3))
    observed = []

    def sized(image: Image.Image, quality: int) -> bytes:
        data = _jpeg_for(image, quality)
        return data + b"\0" * (fit_size - len(data))

    if fit_size == MAX_PREPARED_JPEG_BYTES:
        result = _encode_prepared_jpeg_internal(
            raster,
            pipeline=PreparedJpegPipelineVersion(),
            attempt_observer=observed.append,
            candidate_encoder=sized,
        )
        assert result.byte_size == MAX_PREPARED_JPEG_BYTES
        assert len(observed) == 1
    else:
        with pytest.raises(PreparedJpegError) as exc:
            _encode_prepared_jpeg_internal(
                raster,
                pipeline=PreparedJpegPipelineVersion(),
                attempt_observer=observed.append,
                candidate_encoder=sized,
            )
        assert exc.value.code is PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE
        assert len(observed) == 8


def test_oversized_candidate_advances_and_later_exact_ceiling_is_selected() -> None:
    from document_intake.image_pipeline.jpeg_preparer import _encode_prepared_jpeg_internal

    raster = UncompressedRgbRaster(32, 32, b"\0" * (32 * 32 * 3))
    observed = []
    calls = 0

    def candidate(image: Image.Image, quality: int) -> bytes:
        nonlocal calls
        calls += 1
        size = MAX_PREPARED_JPEG_BYTES + 1 if calls == 1 else MAX_PREPARED_JPEG_BYTES
        data = _jpeg_for(image, quality)
        return data + b"\0" * (size - len(data))

    result = _encode_prepared_jpeg_internal(
        raster,
        pipeline=PreparedJpegPipelineVersion(),
        attempt_observer=observed.append,
        candidate_encoder=candidate,
    )
    assert len(observed) == 2
    assert result.jpeg_quality == observed[-1].jpeg_quality == 90
    assert result.byte_size == MAX_PREPARED_JPEG_BYTES
