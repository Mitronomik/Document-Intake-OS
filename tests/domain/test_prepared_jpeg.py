from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import pytest

from document_intake.application.ports.jpeg_preparation import (
    EncodedPreparedJpeg,
    UncompressedRgbRaster,
)
from document_intake.domain.enums import ActorKind, ColorSpace, PreparedMediaType
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.prepared_jpeg import (
    MAX_PREPARED_JPEG_BYTES,
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_PIPELINE_ID,
    PreparedImageArtifact,
    PreparedJpegError,
    PreparedJpegErrorCode,
)
from document_intake.domain.value_objects import ActorRef, EntityId, Sha256Digest


def eid(n: int) -> EntityId:
    return EntityId(UUID(int=n))


def artifact(size: int = 1) -> PreparedImageArtifact:
    return PreparedImageArtifact(
        eid(1),
        eid(2),
        eid(3),
        eid(4),
        PREPARED_JPEG_PIPELINE_ID,
        1,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        1,
        PreparedMediaType.JPEG,
        ColorSpace.SRGB,
        1,
        1,
        size,
        Sha256Digest("a" * 64),
        95,
        100,
        datetime(2026, 7, 26, tzinfo=UTC),
        ActorRef(eid(5), ActorKind.SYSTEM),
    )


def test_artifact_boundaries_and_error_privacy() -> None:
    assert artifact(MAX_PREPARED_JPEG_BYTES).byte_size == MAX_PREPARED_JPEG_BYTES
    with pytest.raises(InvalidValueError):
        artifact(MAX_PREPARED_JPEG_BYTES + 1)
    error = PreparedJpegError(PreparedJpegErrorCode.JPEG_ENCODING_FAILED)
    assert (
        str(error) == "JPEG_ENCODING_FAILED"
        and repr(error) == "PreparedJpegError(JPEG_ENCODING_FAILED)"
    )


def test_byte_reprs_are_private_and_encoded_result_is_consistent() -> None:
    raw = b"private-pixels!"
    raster = UncompressedRgbRaster(1, 5, raw)
    assert "private-pixels!" not in repr(raster)
    jpeg = b"not-a-real-jpeg"
    encoded = EncodedPreparedJpeg(
        jpeg,
        1,
        1,
        len(jpeg),
        Sha256Digest(sha256(jpeg).hexdigest()),
        95,
        100,
        PREPARED_JPEG_PIPELINE_ID,
        1,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        1,
    )
    assert "not-a-real-jpeg" not in repr(encoded)
