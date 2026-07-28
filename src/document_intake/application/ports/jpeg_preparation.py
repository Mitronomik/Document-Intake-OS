"""Pure prepared-JPEG encoding port."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Protocol

from document_intake.domain.errors import InvalidValueError
from document_intake.domain.prepared_jpeg import (
    JPEG_QUALITY_SEQUENCE,
    JPEG_RESIZE_PERCENT_SEQUENCE,
    MAX_PREPARED_JPEG_BYTES,
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
    PREPARED_JPEG_PIPELINE_ID,
    PREPARED_JPEG_PIPELINE_VERSION,
    PreparedJpegPipelineVersion,
)
from document_intake.domain.value_objects import Sha256Digest


@dataclass(frozen=True, slots=True)
class UncompressedRgbRaster:
    width: int
    height: int
    rgb_pixels: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.width) is not int or self.width < 1:
            raise InvalidValueError("uncompressed_rgb_raster.width: invalid_value")
        if type(self.height) is not int or self.height < 1:
            raise InvalidValueError("uncompressed_rgb_raster.height: invalid_value")
        if (
            type(self.rgb_pixels) is not bytes
            or len(self.rgb_pixels) != self.width * self.height * 3
        ):
            raise InvalidValueError("uncompressed_rgb_raster.rgb_pixels: invalid_length")


@dataclass(frozen=True, slots=True)
class EncodedPreparedJpeg:
    jpeg_bytes: bytes = field(repr=False)
    width: int
    height: int
    byte_size: int
    sha256: Sha256Digest
    jpeg_quality: int
    resize_percent: int
    pipeline_id: str
    pipeline_version: int
    output_contract_id: str
    output_contract_version: int

    def __post_init__(self) -> None:
        if type(self.jpeg_bytes) is not bytes or not self.jpeg_bytes:
            raise InvalidValueError("encoded_prepared_jpeg.jpeg_bytes: invalid_value")
        if type(self.width) is not int or self.width < 1:
            raise InvalidValueError("encoded_prepared_jpeg.width: invalid_value")
        if type(self.height) is not int or self.height < 1:
            raise InvalidValueError("encoded_prepared_jpeg.height: invalid_value")
        if (
            type(self.byte_size) is not int
            or self.byte_size != len(self.jpeg_bytes)
            or not 1 <= self.byte_size <= MAX_PREPARED_JPEG_BYTES
        ):
            raise InvalidValueError("encoded_prepared_jpeg.byte_size: invalid_value")
        if self.sha256 != Sha256Digest(sha256(self.jpeg_bytes).hexdigest()):
            raise InvalidValueError("encoded_prepared_jpeg.sha256: mismatch")
        if self.jpeg_quality not in JPEG_QUALITY_SEQUENCE:
            raise InvalidValueError("encoded_prepared_jpeg.jpeg_quality: invalid_value")
        if self.resize_percent not in JPEG_RESIZE_PERCENT_SEQUENCE:
            raise InvalidValueError("encoded_prepared_jpeg.resize_percent: invalid_value")
        if (self.pipeline_id, self.pipeline_version) != (
            PREPARED_JPEG_PIPELINE_ID,
            PREPARED_JPEG_PIPELINE_VERSION,
        ):
            raise InvalidValueError("encoded_prepared_jpeg.pipeline: invalid_identity")
        if (self.output_contract_id, self.output_contract_version) != (
            PREPARED_JPEG_OUTPUT_CONTRACT_ID,
            PREPARED_JPEG_OUTPUT_CONTRACT_VERSION,
        ):
            raise InvalidValueError("encoded_prepared_jpeg.output_contract: invalid_identity")


class PreparedJpegEncoderPort(Protocol):
    def encode_prepared_jpeg(
        self, raster: UncompressedRgbRaster, *, pipeline: PreparedJpegPipelineVersion
    ) -> EncodedPreparedJpeg: ...
