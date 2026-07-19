from __future__ import annotations

import shutil

from document_intake.domain.enums import ArtifactKind
from document_intake.storage.filesystem import ImmutableFilesystemStorage

from .conftest import StaticKeyProvider, aware_now, entity_id
from .test_filesystem_publication import object_path


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
    rendered = repr(report)
    assert str(tmp_path) not in rendered
    assert "healthy" not in rendered.lower()
    assert invalid_path.exists()


def test_valid_envelope_at_noncanonical_path_is_invalid_not_healthy(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=aware_now(),
    )
    source = object_path(tmp_path, record.artifact_id)
    other_id = entity_id()
    duplicate_path = object_path(tmp_path, other_id)
    duplicate_path.parent.mkdir(parents=True)
    shutil.copyfile(source, duplicate_path)
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
