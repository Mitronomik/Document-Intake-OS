"""Pure prepared-JPEG encoding port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from document_intake.domain.errors import InvalidValueError
from document_intake.domain.prepared_jpeg import PreparedJpegPipelineVersion
from document_intake.domain.value_objects import Sha256Digest


@dataclass(frozen=True, slots=True)
class UncompressedRgbRaster:
    width: int
    height: int
    rgb_pixels: bytes

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
    jpeg_bytes: bytes
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


class PreparedJpegEncoderPort(Protocol):
    def encode_prepared_jpeg(
        self, raster: UncompressedRgbRaster, *, pipeline: PreparedJpegPipelineVersion
    ) -> EncodedPreparedJpeg: ...
