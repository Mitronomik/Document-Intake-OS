from __future__ import annotations

import datetime
import os
from pathlib import Path
from uuid import uuid4

import pytest

from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.storage.errors import StorageError, StorageErrorCode
from document_intake.storage.filesystem import ImmutableFilesystemStorage, is_windows_reparse_point

from .conftest import StaticKeyProvider


def create_synthetic_symlink(link: Path, target: Path, *, directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows runner cannot create synthetic symlink without privilege")
        raise


def test_root_symlink_rejected(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    create_synthetic_symlink(link, target, directory=True)
    with pytest.raises(StorageError) as error:
        ImmutableFilesystemStorage(link, StaticKeyProvider())
    assert error.value.code is StorageErrorCode.ROOT_INVALID


def test_objects_symlink_rejected(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    create_synthetic_symlink(tmp_path / "objects", target, directory=True)
    with pytest.raises(StorageError) as error:
        ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    assert error.value.code is StorageErrorCode.ROOT_INVALID


def test_reparse_detection_without_windows_attribute(tmp_path) -> None:
    assert is_windows_reparse_point(tmp_path) is False


class FakeStat:
    st_file_attributes = 0x400


def test_windows_reparse_attribute_detection(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(Path, "stat", lambda self, follow_symlinks=False: FakeStat())
    assert is_windows_reparse_point(tmp_path) is True


def test_final_symlink_is_not_followed(tmp_path) -> None:
    storage = ImmutableFilesystemStorage(tmp_path, StaticKeyProvider())
    record = storage.publish_bytes(
        artifact_id=EntityId(uuid4()),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=b"payload",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    uuid_hex = record.artifact_id.value.hex
    final = tmp_path / "objects" / uuid_hex[:2] / uuid_hex[2:4] / f"{record.artifact_id}.diosobj"
    final.unlink()
    create_synthetic_symlink(final, tmp_path / "outside", directory=False)
    with pytest.raises(StorageError):
        storage.read_bytes(expected=record)
