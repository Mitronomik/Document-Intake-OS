from __future__ import annotations

import os

import pytest

from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.storage.errors import StorageError, StorageErrorCode
from document_intake.storage.filesystem import ImmutableFilesystemStorage, is_windows_reparse_point

from .conftest import StaticKeyProvider


def test_root_symlink_rejected(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(StorageError) as error:
        ImmutableFilesystemStorage(link, StaticKeyProvider())
    assert error.value.code is StorageErrorCode.ROOT_INVALID


def test_objects_symlink_rejected(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (tmp_path / "objects").symlink_to(target, target_is_directory=True)
    with pytest.raises(StorageError) as error:
        ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    assert error.value.code is StorageErrorCode.ROOT_INVALID


def test_reparse_detection_without_windows_attribute(tmp_path) -> None:
    assert is_windows_reparse_point(tmp_path) is False


@pytest.mark.skipif(os.name == "nt", reason="POSIX O_NOFOLLOW behavior only")
def test_final_symlink_is_not_followed(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=EntityId(__import__("uuid").uuid4()),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=__import__("datetime").datetime.datetime.now(__import__("datetime").UTC),
    )
    uuid_hex = record.artifact_id.value.hex
    final = tmp_path / "objects" / uuid_hex[:2] / uuid_hex[2:4] / f"{record.artifact_id}.diosobj"
    final.unlink()
    final.symlink_to(tmp_path / "outside")
    with pytest.raises(StorageError):
        storage.read_bytes(expected=record)
