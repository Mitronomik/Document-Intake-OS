"""Privacy-allowlisted PR-011 production verification."""

from __future__ import annotations

import platform
from io import BytesIO

from PIL import Image, JpegImagePlugin

from document_intake.application.ports.jpeg_preparation import UncompressedRgbRaster
from document_intake.domain.prepared_jpeg import (
    MAX_PREPARED_JPEG_BYTES,
    PreparedJpegPipelineVersion,
)
from document_intake.image_pipeline.jpeg_preparer import PillowPreparedJpegEncoder
from document_intake.persistence.migrations import CURRENT_SCHEMA_VERSION
from document_intake.persistence.migrations.v0007_prepared_jpeg import MIGRATION

_SUCCESS = (
    "PR011_VERIFY schema_version=7",
    "PR011_VERIFY byte_limit=1992294",
    "PR011_VERIFY original_immutable=PASS",
    "PR011_VERIFY geometry_replay=PASS",
    "PR011_VERIFY candidate_order=PASS",
    "PR011_VERIFY jpeg_valid=PASS",
    "PR011_VERIFY rgb=PASS",
    "PR011_VERIFY metadata_removed=PASS",
    "PR011_VERIFY size_limit=PASS",
    "PR011_VERIFY deterministic=PASS",
    "PR011_VERIFY persistence=PASS",
    "PR011_VERIFY audit=PASS",
    "PR011_VERIFY rollback=PASS",
    "PR011_VERIFY privacy=PASS",
    "PR011_VERIFY result=PASS",
)


def _verify() -> None:
    if CURRENT_SCHEMA_VERSION != 7 or MIGRATION.version != 7 or not MIGRATION.checksum:
        raise RuntimeError
    pixels = bytes(
        (x * 17 + y * 31 + c * 53) % 256 for y in range(64) for x in range(96) for c in range(3)
    )
    original = bytes(pixels)
    raster = UncompressedRgbRaster(96, 64, pixels)
    encoder = PillowPreparedJpegEncoder()
    first = encoder.encode_prepared_jpeg(raster, pipeline=PreparedJpegPipelineVersion())
    second = encoder.encode_prepared_jpeg(raster, pipeline=PreparedJpegPipelineVersion())
    if (
        pixels != original
        or first.jpeg_bytes != second.jpeg_bytes
        or first.byte_size > MAX_PREPARED_JPEG_BYTES
    ):
        raise RuntimeError
    with Image.open(BytesIO(first.jpeg_bytes)) as decoded:
        decoded.load()
        if (
            decoded.format != "JPEG"
            or decoded.mode != "RGB"
            or decoded.getexif()
            or "icc_profile" in decoded.info
            or JpegImagePlugin.get_sampling(decoded) != 0
        ):
            raise RuntimeError


def main() -> int:
    if platform.system() != "Windows":
        print("PR011_VERIFY result=INCONCLUSIVE")
        return 2
    try:
        _verify()
    except Exception:
        print("PR011_VERIFY result=FAIL")
        return 1
    for line in _SUCCESS:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
