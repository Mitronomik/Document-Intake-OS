from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, JpegImagePlugin

from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.domain.prepared_jpeg import (
    JPEG_QUALITY_SEQUENCE,
    JPEG_RESIZE_PERCENT_SEQUENCE,
    MAX_PREPARED_JPEG_BYTES,
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_PIPELINE_ID,
    PreparedJpegError,
    PreparedJpegErrorCode,
    PreparedJpegPipelineVersion,
)
from document_intake.image_pipeline.jpeg_preparer import (
    PillowPreparedJpegEncoder,
    _scaled_dimension,
)


def test_pr011_enc_004_structural_jpeg_contract() -> None:
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
    assert first.byte_size == len(first.jpeg_bytes)
    assert first.sha256.value == sha256(first.jpeg_bytes).hexdigest()
    assert first.pipeline_id == PREPARED_JPEG_PIPELINE_ID
    assert first.pipeline_version == 1
    assert first.output_contract_id == PREPARED_JPEG_OUTPUT_CONTRACT_ID
    assert first.output_contract_version == 1
    assert b"synthetic-source" not in first.jpeg_bytes
    with Image.open(BytesIO(first.jpeg_bytes)) as decoded:
        decoded.load()
        assert decoded.format == "JPEG"
        assert decoded.mode == "RGB"
        assert "A" not in decoded.getbands()
        assert decoded.size == (first.width, first.height)
        assert not decoded.getexif()
        assert JpegImagePlugin.get_sampling(decoded) == 0
        assert not decoded.info.get("progressive")
        assert not decoded.info.get("progression")
        for key in (
            "icc_profile",
            "xmp",
            "XML:com.adobe.xmp",
            "iptc",
            "comment",
            "dpi",
            "thumbnail",
        ):
            assert key not in decoded.info


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


def test_pr011_enc_002_complete_48_attempt_ordering() -> None:
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
    assert exc.value.__cause__ is None
    assert "path" not in repr(exc.value).lower()
    assert observed == list(_iter_candidate_attempts(raster))
    assert len(observed) == 48
    assert [(item.resize_percent, item.jpeg_quality) for item in observed] == [
        (scale, quality)
        for scale in JPEG_RESIZE_PERCENT_SEQUENCE
        for quality in JPEG_QUALITY_SEQUENCE
    ]
    assert [(item.width, item.height) for item in observed[::8]] == [
        (2400, 2400),
        (2160, 2160),
        (1920, 1920),
        (1680, 1680),
        (1440, 1440),
        (1200, 1200),
    ]


def test_pr011_enc_003_exact_byte_ceiling_and_ceiling_plus_one() -> None:
    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline.jpeg_preparer import _encode_prepared_jpeg_internal

    raster = UncompressedRgbRaster(32, 32, b"\0" * (32 * 32 * 3))
    observed = []

    calls = 0

    def sized(image: Image.Image, quality: int) -> bytes:
        nonlocal calls
        calls += 1
        data = _jpeg_for(image, quality)
        size = MAX_PREPARED_JPEG_BYTES + 1 if calls == 1 else MAX_PREPARED_JPEG_BYTES
        return data + b"\0" * (size - len(data))

    result = _encode_prepared_jpeg_internal(
        raster,
        pipeline=PreparedJpegPipelineVersion(),
        attempt_observer=observed.append,
        candidate_encoder=sized,
    )
    assert calls == len(observed) == 2
    assert result.byte_size == MAX_PREPARED_JPEG_BYTES
    assert result.sha256.value == sha256(result.jpeg_bytes).hexdigest()
    assert result.jpeg_quality == 90

    failed_result = None
    with pytest.raises(PreparedJpegError) as exc:
        failed_result = _encode_prepared_jpeg_internal(
            raster,
            pipeline=PreparedJpegPipelineVersion(),
            candidate_encoder=lambda image, quality: (
                _jpeg_for(image, quality)
                + b"\0" * (MAX_PREPARED_JPEG_BYTES + 1 - len(_jpeg_for(image, quality)))
            ),
        )
    assert exc.value.code is PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE
    assert failed_result is None


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


def _encoded_image_bytes(image: Image.Image, *, format: str = "JPEG", **options: object) -> bytes:
    output = BytesIO()
    image.save(output, format=format, **options)
    return output.getvalue()


@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param(
            lambda: _encoded_image_bytes(Image.new("RGB", (8, 8)), format="PNG"), id="png"
        ),
        pytest.param(lambda: _encoded_image_bytes(Image.new("L", (8, 8))), id="grayscale"),
        pytest.param(lambda: _encoded_image_bytes(Image.new("CMYK", (8, 8))), id="cmyk"),
        pytest.param(lambda: _encoded_image_bytes(Image.new("RGB", (9, 8))), id="wrong-dimensions"),
        pytest.param(
            lambda: _encoded_image_bytes(Image.new("RGB", (8, 8)), exif=b"Exif\0\0synthetic"),
            id="exif",
        ),
        pytest.param(
            lambda: _encoded_image_bytes(Image.new("RGB", (8, 8)), icc_profile=b"synthetic"),
            id="icc",
        ),
        pytest.param(
            lambda: _encoded_image_bytes(Image.new("RGB", (8, 8)), progressive=True),
            id="progressive",
        ),
        pytest.param(
            lambda: _encoded_image_bytes(Image.new("RGB", (8, 8)), subsampling=2),
            id="non-444",
        ),
    ],
)
def test_invalid_generated_jpeg_structure_stops_after_first_attempt(candidate) -> None:  # type: ignore[no-untyped-def]
    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline.jpeg_preparer import _encode_prepared_jpeg_internal

    observed = []
    raster = UncompressedRgbRaster(8, 8, b"\0" * (8 * 8 * 3))
    with pytest.raises(PreparedJpegError) as exc:
        _encode_prepared_jpeg_internal(
            raster,
            pipeline=PreparedJpegPipelineVersion(),
            attempt_observer=observed.append,
            candidate_encoder=lambda image, quality: candidate(),
        )
    assert exc.value.code is PreparedJpegErrorCode.JPEG_ENCODING_FAILED
    assert exc.value.__cause__ is None
    assert len(observed) == 1


def test_image_frombytes_failure_is_sanitized_and_starts_no_attempt(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline import jpeg_preparer

    monkeypatch.setattr(
        jpeg_preparer.Image,
        "frombytes",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("private-source.jpg")),
    )
    observed = []
    with pytest.raises(PreparedJpegError) as exc:
        jpeg_preparer._encode_prepared_jpeg_internal(
            UncompressedRgbRaster(8, 8, b"\0" * 192),
            pipeline=PreparedJpegPipelineVersion(),
            attempt_observer=observed.append,
        )
    assert exc.value.code is PreparedJpegErrorCode.JPEG_ENCODING_FAILED
    assert exc.value.__cause__ is None
    assert "private-source" not in repr(exc.value)
    assert observed == []


def test_candidate_save_failure_is_sanitized_and_stops_search() -> None:
    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline.jpeg_preparer import _encode_prepared_jpeg_internal

    observed = []
    with pytest.raises(PreparedJpegError) as exc:
        _encode_prepared_jpeg_internal(
            UncompressedRgbRaster(8, 8, b"\0" * 192),
            pipeline=PreparedJpegPipelineVersion(),
            attempt_observer=observed.append,
            candidate_encoder=lambda image, quality: (_ for _ in ()).throw(
                OSError("private-output.jpg")
            ),
        )
    assert exc.value.code is PreparedJpegErrorCode.JPEG_ENCODING_FAILED
    assert exc.value.__cause__ is None
    assert len(observed) == 1


@pytest.mark.parametrize("metadata_key", ["xmp", "XML:com.adobe.xmp", "iptc", "comment"])
def test_unreliable_metadata_markers_are_structural_failures(
    monkeypatch, metadata_key: str
) -> None:  # type: ignore[no-untyped-def]
    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline import jpeg_preparer

    class Decoded:
        format = "JPEG"
        mode = "RGB"
        size = (8, 8)

        def __init__(self) -> None:
            self.info = {metadata_key: b"synthetic"}

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *args):  # type: ignore[no-untyped-def]
            return False

        def load(self) -> None:
            return None

        def getexif(self) -> dict[object, object]:
            return {}

    monkeypatch.setattr(jpeg_preparer.Image, "open", lambda stream: Decoded())
    monkeypatch.setattr(jpeg_preparer.JpegImagePlugin, "get_sampling", lambda image: 0)
    observed = []
    with pytest.raises(PreparedJpegError) as exc:
        jpeg_preparer._encode_prepared_jpeg_internal(
            UncompressedRgbRaster(8, 8, b"\0" * 192),
            pipeline=PreparedJpegPipelineVersion(),
            attempt_observer=observed.append,
            candidate_encoder=lambda image, quality: b"synthetic",
        )
    assert exc.value.code is PreparedJpegErrorCode.JPEG_ENCODING_FAILED
    assert exc.value.__cause__ is None
    assert len(observed) == 1


def test_resize_failure_is_sanitized_before_scaled_attempt_is_observed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from document_intake.domain.prepared_jpeg import PreparedJpegError, PreparedJpegErrorCode
    from document_intake.image_pipeline import jpeg_preparer

    original_resize = jpeg_preparer.Image.Image.resize

    def fail_resize(self, size, resample=None, box=None, reducing_gap=None):  # type: ignore[no-untyped-def]
        raise OSError("private-resize-dimensions")

    monkeypatch.setattr(jpeg_preparer.Image.Image, "resize", fail_resize)
    observed = []

    def oversized(image: Image.Image, quality: int) -> bytes:
        data = _jpeg_for(image, quality)
        return data + b"\0" * (MAX_PREPARED_JPEG_BYTES + 1 - len(data))

    with pytest.raises(PreparedJpegError) as exc:
        jpeg_preparer._encode_prepared_jpeg_internal(
            UncompressedRgbRaster(2400, 2400, b"\0" * (2400 * 2400 * 3)),
            pipeline=PreparedJpegPipelineVersion(),
            attempt_observer=observed.append,
            candidate_encoder=oversized,
        )
    assert original_resize is not fail_resize
    assert exc.value.code is PreparedJpegErrorCode.JPEG_ENCODING_FAILED
    assert exc.value.__cause__ is None
    assert len(observed) == 8


def test_pr011_enc_001_every_resize_uses_original_uncompressed_raster(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from document_intake.image_pipeline import jpeg_preparer

    original_resize = jpeg_preparer.Image.Image.resize
    resize_calls: list[tuple[int, tuple[int, int], object, int]] = []
    encoded_images: list[int] = []

    def tracked_resize(self, size, resample=None, box=None, reducing_gap=None):  # type: ignore[no-untyped-def]
        result = original_resize(self, size, resample, box, reducing_gap)
        resize_calls.append((id(self), size, resample, id(result)))
        return result

    monkeypatch.setattr(jpeg_preparer.Image.Image, "resize", tracked_resize)
    source_pixels = b"\0" * (2400 * 2400 * 3)
    raster = UncompressedRgbRaster(2400, 2400, source_pixels)

    def candidate(image: Image.Image, quality: int) -> bytes:
        encoded_images.append(id(image))
        data = _jpeg_for(image, quality)
        return data + b"\0" * (MAX_PREPARED_JPEG_BYTES + 1 - len(data))

    with pytest.raises(PreparedJpegError) as exc:
        jpeg_preparer._encode_prepared_jpeg_internal(
            raster,
            pipeline=PreparedJpegPipelineVersion(),
            candidate_encoder=candidate,
        )
    assert exc.value.code is PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE
    assert len(resize_calls) == 5
    original_id = encoded_images[0]
    assert all(call[0] == original_id for call in resize_calls)
    assert [call[1] for call in resize_calls] == [
        (2160, 2160),
        (1920, 1920),
        (1680, 1680),
        (1440, 1440),
        (1200, 1200),
    ]
    assert all(call[2] == Image.Resampling.LANCZOS for call in resize_calls)
    scale_ids = [original_id, *(call[3] for call in resize_calls)]
    assert len(set(scale_ids)) == 6
    for index, image_id in enumerate(scale_ids):
        assert encoded_images[index * 8 : (index + 1) * 8] == [image_id] * 8
    assert raster.rgb_pixels == source_pixels


def test_pr011_enc_005_no_intermediate_candidate_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from document_intake.image_pipeline.jpeg_preparer import _encode_prepared_jpeg_internal

    monkeypatch.setattr(
        Path,
        "write_bytes",
        lambda *args, **kwargs: pytest.fail("encoder attempted filesystem publication"),
    )
    raster = UncompressedRgbRaster(32, 32, b"\0" * (32 * 32 * 3))
    candidates: list[bytes] = []
    observed = []

    def candidate(image: Image.Image, quality: int) -> bytes:
        data = _jpeg_for(image, quality)
        size = MAX_PREPARED_JPEG_BYTES + 1 if not candidates else MAX_PREPARED_JPEG_BYTES
        value = data + bytes([quality]) * (size - len(data))
        candidates.append(value)
        return value

    result = _encode_prepared_jpeg_internal(
        raster,
        pipeline=PreparedJpegPipelineVersion(),
        attempt_observer=observed.append,
        candidate_encoder=candidate,
    )
    assert len(candidates) == len(observed) == 2
    assert result.jpeg_bytes == candidates[1]
    assert result.jpeg_bytes != candidates[0]
    assert candidates[0] not in result.jpeg_bytes
    assert result.sha256.value != sha256(candidates[0]).hexdigest()
    assert all(not hasattr(attempt, "jpeg_bytes") for attempt in observed)

    failed_result = None
    with pytest.raises(PreparedJpegError) as exc:
        failed_result = _encode_prepared_jpeg_internal(
            raster,
            pipeline=PreparedJpegPipelineVersion(),
            candidate_encoder=lambda image, quality: (
                _jpeg_for(image, quality)
                + b"\0" * (MAX_PREPARED_JPEG_BYTES + 1 - len(_jpeg_for(image, quality)))
            ),
        )
    assert exc.value.code is PreparedJpegErrorCode.SIZE_LIMIT_UNREACHABLE
    assert failed_result is None
