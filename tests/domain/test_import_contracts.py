from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from document_intake.domain.entities.imports import ImportWarning, SourceFile, UploadBatch
from document_intake.domain.enums import ImportWarningCode, SourceMediaType, UploadBatchStatus
from document_intake.domain.errors import InvalidValueError
from document_intake.domain.value_objects import ActorRef, EntityId
from document_intake.domain.value_objects.imports import (
    BatchNumber,
    PerceptualHash,
    Sha256Digest,
    SourceBasename,
)


def eid():
    return EntityId(uuid4())


def actor():
    from document_intake.domain.enums import ActorKind

    return ActorRef(eid(), ActorKind.OPERATOR)


def test_exact_import_enums():
    assert [x.value for x in UploadBatchStatus] == [
        "NEW",
        "PROCESSING",
        "NEEDS_REVIEW",
        "READY",
        "ARCHIVED",
    ]
    assert [x.value for x in SourceMediaType] == ["JPEG", "PNG", "HEIF"]
    assert [x.value for x in ImportWarningCode] == [
        "EXACT_DUPLICATE",
        "PERCEPTUAL_SIMILARITY",
        "EXTENSION_CONTENT_MISMATCH",
    ]


def test_exact_entity_fields_and_no_quality_assessment():
    assert [f.name for f in fields(UploadBatch)] == [
        "id",
        "number",
        "created_at",
        "created_by",
        "status",
        "source_file_ids",
    ]
    assert [f.name for f in fields(SourceFile)] == [
        "id",
        "batch_id",
        "original_artifact_id",
        "original_basename",
        "detected_media_type",
        "byte_size",
        "sha256",
        "perceptual_hash",
        "width",
        "height",
        "exif_orientation",
        "imported_at",
        "imported_by",
    ]
    assert [f.name for f in fields(ImportWarning)] == [
        "code",
        "source_file_id",
        "related_source_file_id",
        "perceptual_distance",
        "algorithm_id",
        "algorithm_version",
    ]
    assert not hasattr(SourceFile, "quality_assessment")


def test_value_object_boundaries_and_repr():
    assert BatchNumber("A" * 64).value == "A" * 64
    with pytest.raises(InvalidValueError):
        BatchNumber("A" * 65)
    assert SourceBasename("x" * 255).value == "x" * 255
    for bad in ["", "x" * 256, ".", "..", "a/b", "a\\b", "a\x00b", "a\x1fb", "a\x7fb"]:
        with pytest.raises(InvalidValueError):
            SourceBasename(bad)
    with pytest.raises(InvalidValueError):
        Sha256Digest("A" * 64)
    with pytest.raises(InvalidValueError):
        PerceptualHash("DHASH64", True, 64, "0" * 16)
    assert "redacted" in repr(SourceBasename("x"))
    assert "redacted" in repr(Sha256Digest("a" * 64))
    assert "redacted" in repr(PerceptualHash("DHASH64", 1, 64, "0" * 16))


def test_batch_immutable_append_and_utc():
    first = eid()
    second = eid()
    batch = UploadBatch(
        eid(),
        BatchNumber("B1"),
        datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2))),
        actor(),
        UploadBatchStatus.NEW,
        (first,),
    )
    assert batch.created_at.tzinfo == UTC
    updated = batch.append_source_file_id(second)
    assert batch.source_file_ids == (first,)
    assert updated.source_file_ids == (first, second)
    with pytest.raises(InvalidValueError):
        updated.append_source_file_id(second)
    with pytest.raises(FrozenInstanceError):
        batch.status = UploadBatchStatus.READY  # type: ignore[misc]
    with pytest.raises(InvalidValueError):
        UploadBatch(
            eid(), BatchNumber("B2"), datetime(2026, 1, 1), actor(), UploadBatchStatus.NEW, ()
        )


def test_warning_invariants():
    source = eid()
    related = eid()
    ImportWarning(ImportWarningCode.EXACT_DUPLICATE, source, related, None, None, None)
    ImportWarning(ImportWarningCode.PERCEPTUAL_SIMILARITY, source, related, 8, "DHASH64", 1)
    ImportWarning(ImportWarningCode.EXTENSION_CONTENT_MISMATCH, source, None, None, None, None)
    with pytest.raises(InvalidValueError):
        ImportWarning(ImportWarningCode.EXACT_DUPLICATE, source, None, None, None, None)
    with pytest.raises(InvalidValueError):
        ImportWarning(ImportWarningCode.PERCEPTUAL_SIMILARITY, source, related, True, "DHASH64", 1)
    with pytest.raises(InvalidValueError):
        ImportWarning(ImportWarningCode.PERCEPTUAL_SIMILARITY, source, source, 1, "DHASH64", 1)
