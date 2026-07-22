"""Deterministic synthetic, non-document MPO fixtures for decoder tests."""

from __future__ import annotations

import io

from PIL import Image


def synthetic_mpo(
    primary: Image.Image,
    secondary: Image.Image,
    *,
    orientation: int | None = None,
) -> bytes:
    """Encode two synthetic frames as an MPO using Pillow's pinned writer."""
    stream = io.BytesIO()
    options: dict[str, object] = {
        "save_all": True,
        "append_images": [secondary],
        "quality": 95,
        "subsampling": 0,
    }
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation
        options["exif"] = exif
    primary.save(stream, format="MPO", **options)
    return stream.getvalue()


def synthetic_pattern(size: tuple[int, int], variant: int) -> Image.Image:
    """Return a visually distinct PII-free RGB pattern."""
    width, height = size
    image = Image.new("RGB", size)
    image.putdata(
        [
            (
                (x * 29 + y * 7 + variant * 31) % 256,
                (x * 5 + y * 37 + variant * 17) % 256,
                (x * 19 + y * 11 + variant * 43) % 256,
            )
            for y in range(height)
            for x in range(width)
        ]
    )
    return image
