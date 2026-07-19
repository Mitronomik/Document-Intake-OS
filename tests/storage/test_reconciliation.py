from __future__ import annotations

import shutil

import pytest

from document_intake.domain.enums import ArtifactKind
from document_intake.storage.errors import StorageError, StorageErrorCode
from document_intake.storage.filesystem import ImmutableFilesystemStorage

from .conftest import StaticKeyProvider, aware_now, entity_id
from .test_filesystem_publication import object_path


def _copy_to_noncanonical(root, source_record, target_id=None):
    duplicate_id = target_id or entity_id()
    duplicate = object_path(root, duplicate_id)
    duplicate.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(object_path(root, source_record.artifact_id), duplicate)
    return duplicate


def test_reconciliation_healthy_missing_invalid_orphan_and_temporary(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    healthy = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"healthy",
        created_at=aware_now(),
    )
    missing = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"missing",
        created_at=aware_now(),
    )
    invalid = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"invalid",
        created_at=aware_now(),
    )
    orphan = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"orphan",
        created_at=aware_now(),
    )
    object_path(tmp_path, missing.artifact_id).unlink()
    invalid_path = object_path(tmp_path, invalid.artifact_id)
    invalid_path.write_bytes(invalid_path.read_bytes()[:-1] + b"x")
    temp = (
        object_path(tmp_path, healthy.artifact_id).parent
        / ".tmp-00000000-0000-0000-0000-000000000000.diosobj"
    )
    temp.write_bytes(b"encrypted-temp")
    report = storage.reconcile(expected=(healthy, missing, invalid))
    assert report.counts == {"healthy": 1, "missing": 1, "invalid": 1, "orphan": 1, "temporary": 1}
    assert report.orphan[0].artifact_id == orphan.artifact_id
    assert invalid_path.exists()


def test_reconciliation_report_repr_excludes_sensitive_values(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    secret_plaintext = b"privacy-secret-marker-006"
    key_marker = "4b" * 32
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=secret_plaintext,
        created_at=aware_now(),
    )
    report = storage.reconcile(expected=(record,))
    rendered = " ".join(
        (
            repr(report),
            *(
                repr(item)
                for group in (
                    report.healthy,
                    report.missing,
                    report.invalid,
                    report.orphan,
                    report.temporary,
                )
                for item in group
            ),
        )
    )
    forbidden = (
        str(tmp_path),
        f"objects/{record.artifact_id.value.hex[:2]}/{record.artifact_id.value.hex[2:4]}",
        f"{record.artifact_id}.diosobj",
        str(record.artifact_id),
        secret_plaintext.decode("ascii"),
        key_marker,
        record.plaintext_sha256,
        record.ciphertext_sha256,
        '"algorithm"',
        "Traceback",
        "InvalidTag",
    )
    assert all(value not in rendered for value in forbidden)
    assert "healthy" in rendered.lower()


def test_valid_envelope_at_noncanonical_path_is_invalid_not_healthy(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    _copy_to_noncanonical(tmp_path, record)
    report = storage.reconcile(expected=(record,))
    assert report.counts["healthy"] == 1
    assert report.counts["invalid"] == 1


def test_malformed_orphan_is_invalid(tmp_path) -> None:
    ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    artifact_id = entity_id()
    path = object_path(tmp_path, artifact_id)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not an envelope")
    report = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider()).reconcile(expected=())
    assert report.counts["invalid"] == 1


def test_canonical_expected_only_is_healthy(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    assert storage.reconcile(expected=(record,)).counts == {
        "healthy": 1,
        "missing": 0,
        "invalid": 0,
        "orphan": 0,
        "temporary": 0,
    }


def test_canonical_orphan_only_is_orphan(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    assert storage.reconcile(expected=()).counts["orphan"] == 1


def test_duplicate_expected_artifact_is_order_independent(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    duplicate_id = entity_id()
    # Alphabetically earlier path proves a noncanonical duplicate cannot consume the ID first.
    while str(duplicate_id) > str(record.artifact_id):
        duplicate_id = entity_id()
    _copy_to_noncanonical(tmp_path, record, duplicate_id)
    report = storage.reconcile(expected=(record,))
    assert report.counts["healthy"] == 1
    assert report.counts["invalid"] == 1


def test_duplicate_orphan_artifact_id_is_invalid(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    _copy_to_noncanonical(tmp_path, record)
    report = storage.reconcile(expected=())
    assert report.counts["orphan"] == 1
    assert report.counts["invalid"] == 1


def test_two_noncanonical_copies_are_invalid(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    canonical = object_path(tmp_path, record.artifact_id)
    first = _copy_to_noncanonical(tmp_path, record)
    second = _copy_to_noncanonical(tmp_path, record)
    canonical.unlink()
    assert first.exists()
    assert second.exists()
    report = storage.reconcile(expected=())
    assert report.counts["orphan"] == 0
    assert report.counts["invalid"] == 2


def test_unsafe_objects_directory_fails_closed(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    objects = tmp_path / "objects"
    shutil.rmtree(objects)
    objects.write_text("not a directory")
    with pytest.raises(StorageError) as error:
        storage.reconcile(expected=())
    assert error.value.code is StorageErrorCode.ROOT_INVALID
    assert str(tmp_path) not in str(error.value)


def test_malformed_expected_object_is_reported_invalid_once(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    path = object_path(tmp_path, record.artifact_id)
    path.write_bytes(b"not an envelope")

    report = storage.reconcile(expected=(record,))

    assert report.counts == {
        "healthy": 0,
        "missing": 0,
        "invalid": 1,
        "orphan": 0,
        "temporary": 0,
    }
    assert report.invalid[0].artifact_id == record.artifact_id
