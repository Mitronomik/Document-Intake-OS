from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image
from synthetic_mpo import synthetic_mpo, synthetic_pattern

from document_intake.application.ports.media import DecodedQualityMedia
from document_intake.domain.enums import QualityIssueCode, QualityIssueSeverity, SourceMediaType
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.image_quality import (
    ImageQualityPolicy,
    ImageQualitySeverityRule,
    QualityPolicyVersion,
)
from document_intake.image_pipeline.media_decoder import PillowMediaDecoder, dhash64
from document_intake.image_pipeline.quality_assessor import calculate_quality_metrics


def png(mode="RGB"):
    img = Image.new(mode, (2, 1), (10, 20, 30, 128) if mode == "RGBA" else (10, 20, 30))
    b = BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def test_decoded_quality_media_invariants() -> None:
    DecodedQualityMedia(SourceMediaType.PNG, 2, 1, None, 2, 1, b"\x00\x01", 2, 1)
    for kwargs in [
        dict(encoded_width=True),
        dict(exif_orientation=True),
        dict(grayscale_pixels=bytearray(b"12")),
        dict(effective_width=1),
    ]:
        base = dict(
            media_type=SourceMediaType.PNG,
            encoded_width=2,
            encoded_height=1,
            exif_orientation=None,
            effective_width=2,
            effective_height=1,
            grayscale_pixels=b"12",
            grayscale_width=2,
            grayscale_height=1,
        )
        base.update(kwargs)
        with pytest.raises(InvalidValueError):
            DecodedQualityMedia(**base)


def test_quality_decoder_full_resolution_luminance_and_import_compat() -> None:
    content = png()
    before = bytes(content)
    d = PillowMediaDecoder().decode_for_quality(content=content)
    assert content == before and d.grayscale_width == 2 and d.grayscale_height == 1
    assert d.grayscale_pixels == bytes([(299 * 10 + 587 * 20 + 114 * 30 + 500) // 1000]) * 2
    imp = PillowMediaDecoder().decode_for_import(content=content)
    assert (
        imp.grayscale_width == 9 and imp.grayscale_height == 8 and len(imp.grayscale_pixels) == 72
    )
    assert len(dhash64(imp.grayscale_pixels)) == 16


def _policy() -> ImageQualityPolicy:
    return ImageQualityPolicy(
        QualityPolicyVersion("SYNTHETIC_MPO", 1),
        1,
        1,
        Decimal("0"),
        Decimal("0"),
        220,
        Decimal("1"),
        20,
        Decimal("1"),
        235,
        Decimal("1"),
        tuple(
            ImageQualitySeverityRule(code, QualityIssueSeverity.WARNING)
            for code in QualityIssueCode
        ),
    )


def test_mpo_quality_uses_only_oriented_primary_frame_for_all_metrics() -> None:
    primary = synthetic_pattern((18, 12), 5)
    changed_primary = synthetic_pattern((18, 12), 6)
    first_secondary = synthetic_pattern((9, 7), 7)
    changed_secondary = synthetic_pattern((25, 21), 8)
    content = synthetic_mpo(primary, first_secondary, orientation=6)
    secondary_changed_content = synthetic_mpo(primary, changed_secondary, orientation=6)
    primary_changed_content = synthetic_mpo(changed_primary, first_secondary, orientation=6)
    original = bytes(content)
    decoder = PillowMediaDecoder()

    decoded_primary = decoder.decode_for_quality(content=content)
    decoded_secondary_changed = decoder.decode_for_quality(content=secondary_changed_content)
    decoded_primary_changed = decoder.decode_for_quality(content=primary_changed_content)
    primary_metrics = calculate_quality_metrics(decoded_primary, policy=_policy())
    secondary_changed_metrics = calculate_quality_metrics(
        decoded_secondary_changed, policy=_policy()
    )
    primary_changed_metrics = calculate_quality_metrics(decoded_primary_changed, policy=_policy())

    assert content == original
    assert decoded_primary.media_type is SourceMediaType.JPEG
    assert (decoded_primary.encoded_width, decoded_primary.encoded_height) == primary.size
    assert (decoded_primary.effective_width, decoded_primary.effective_height) == (12, 18)
    assert decoded_primary.exif_orientation == 6
    assert decoded_secondary_changed.grayscale_pixels == decoded_primary.grayscale_pixels
    assert (
        decoded_secondary_changed.grayscale_width,
        decoded_secondary_changed.grayscale_height,
    ) == (decoded_primary.grayscale_width, decoded_primary.grayscale_height)
    assert secondary_changed_metrics == primary_metrics
    assert decoded_primary_changed.grayscale_pixels != decoded_primary.grayscale_pixels
    assert primary_changed_metrics != primary_metrics
