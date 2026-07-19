"""Immutable encrypted filesystem storage."""

from __future__ import annotations

import os
import re
import stat
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from document_intake.application.dto.storage import (
    StorageReconciliationItem,
    StorageReconciliationReport,
    StorageReconciliationStatus,
    StoredArtifactRecord,
)
from document_intake.application.ports.storage import StorageKey, StorageKeyProvider
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.storage.envelope import (
    FORMAT_VERSION,
    build_envelope,
    decrypt_envelope,
    parse_envelope,
    sha256_hex,
)
from document_intake.storage.errors import StorageError, StorageErrorCode

_FINAL_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.diosobj$")
_TMP_RE = re.compile(
    r"^\.tmp-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.diosobj$"
)
_WINDOWS_REPARSE_ATTRIBUTE = 0x400


class FilesystemFailurePoint(StrEnum):
    BEFORE_TEMPORARY_CREATION = "before_temporary_creation"
    AFTER_TEMPORARY_CREATION = "after_temporary_creation"
    AFTER_PARTIAL_TEMPORARY_WRITE = "after_partial_temporary_write"
    AFTER_COMPLETE_TEMPORARY_WRITE = "after_complete_temporary_write"
    AFTER_TEMPORARY_FSYNC = "after_temporary_fsync"
    BEFORE_FINAL_PUBLICATION = "before_final_publication"
    AFTER_FINAL_PUBLICATION = "after_final_publication"
    DURING_DIRECTORY_FSYNC = "during_directory_fsync"


@dataclass(frozen=True, slots=True)
class _ManagedPath:
    final: Path
    directory: Path


class _FilesystemOperations:
    """Private OS boundary used by tests for deterministic failure injection."""

    def create_directory(self, path: Path) -> None:
        path.mkdir(exist_ok=True)

    def create_directories(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def open_exclusive_no_follow(self, path: Path) -> int:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        return os.open(path, flags, 0o600)

    def write_all(self, fd: int, data: bytes) -> None:
        total = 0
        while total < len(data):
            written = os.write(fd, data[total:])
            if written <= 0:
                raise OSError
            total += written

    def fsync_file(self, fd: int) -> None:
        os.fsync(fd)

    def close(self, fd: int) -> None:
        os.close(fd)

    def publish_no_replace(self, temporary: Path, final: Path) -> None:
        if os.name == "nt":
            temporary.rename(final)
        else:
            os.link(temporary, final)
            temporary.unlink()

    def unlink(self, path: Path) -> None:
        path.unlink()

    def fsync_directory(self, path: Path) -> None:
        if os.name == "nt":
            return
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def read_bytes_no_follow(self, path: Path) -> bytes:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags)
        try:
            mode = os.fstat(fd).st_mode
            if not stat.S_ISREG(mode):
                raise StorageError(StorageErrorCode.IO_FAILED)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
        finally:
            os.close(fd)


class _FailingFilesystemOperations(_FilesystemOperations):
    def __init__(self, failure_point: FilesystemFailurePoint | None) -> None:
        self.failure_point = failure_point
        self.created_temporary: Path | None = None

    def _fail(self, point: FilesystemFailurePoint) -> None:
        if self.failure_point == point:
            raise OSError

    def open_exclusive_no_follow(self, path: Path) -> int:
        self._fail(FilesystemFailurePoint.BEFORE_TEMPORARY_CREATION)
        fd = super().open_exclusive_no_follow(path)
        self.created_temporary = path
        if self.failure_point == FilesystemFailurePoint.AFTER_TEMPORARY_CREATION:
            os.close(fd)
            raise OSError
        return fd

    def write_all(self, fd: int, data: bytes) -> None:
        if self.failure_point == FilesystemFailurePoint.AFTER_PARTIAL_TEMPORARY_WRITE:
            os.write(fd, data[: max(1, len(data) // 2)])
            raise OSError
        super().write_all(fd, data)
        self._fail(FilesystemFailurePoint.AFTER_COMPLETE_TEMPORARY_WRITE)

    def fsync_file(self, fd: int) -> None:
        super().fsync_file(fd)
        self._fail(FilesystemFailurePoint.AFTER_TEMPORARY_FSYNC)

    def publish_no_replace(self, temporary: Path, final: Path) -> None:
        self._fail(FilesystemFailurePoint.BEFORE_FINAL_PUBLICATION)
        super().publish_no_replace(temporary, final)
        self._fail(FilesystemFailurePoint.AFTER_FINAL_PUBLICATION)

    def fsync_directory(self, path: Path) -> None:
        self._fail(FilesystemFailurePoint.DURING_DIRECTORY_FSYNC)
        super().fsync_directory(path)


def is_windows_reparse_point(path: Path) -> bool:
    try:
        stat_result: Any = path.stat(follow_symlinks=False)
        attribute_name = "st_file_attributes"
        attributes = getattr(stat_result, attribute_name)
    except AttributeError:
        return False
    except OSError:
        raise StorageError(StorageErrorCode.IO_FAILED) from None
    return bool(attributes & _WINDOWS_REPARSE_ATTRIBUTE)


def _is_safe_existing_directory(path: Path) -> bool:
    try:
        st = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(st.st_mode)
        and not stat.S_ISLNK(st.st_mode)
        and not is_windows_reparse_point(path)
    )


def _is_safe_regular_file(path: Path) -> bool:
    try:
        st = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(st.st_mode)
        and not stat.S_ISLNK(st.st_mode)
        and not is_windows_reparse_point(path)
    )


class ImmutableFilesystemStorage:
    def __init__(
        self,
        root: Path,
        key_provider: StorageKeyProvider,
        *,
        filesystem_operations: _FilesystemOperations | None = None,
    ) -> None:
        self._root = Path(root)
        self._key_provider = key_provider
        self._fs = filesystem_operations or _FilesystemOperations()
        if not _is_safe_existing_directory(self._root):
            raise StorageError(StorageErrorCode.ROOT_INVALID)
        objects = self._root / "objects"
        if objects.exists() and not _is_safe_existing_directory(objects):
            raise StorageError(StorageErrorCode.ROOT_INVALID)
        if not objects.exists():
            try:
                self._fs.create_directory(objects)
            except OSError:
                raise StorageError(StorageErrorCode.ROOT_INVALID) from None
        if not _is_safe_existing_directory(objects):
            raise StorageError(StorageErrorCode.ROOT_INVALID)

    def __repr__(self) -> str:
        return "ImmutableFilesystemStorage(<redacted>)"

    def _current_key(self) -> StorageKey:
        try:
            key = self._key_provider.get_current_key()
        except StorageError:
            raise
        except Exception:
            raise StorageError(StorageErrorCode.KEY_UNAVAILABLE) from None
        if type(key) is not StorageKey:
            raise StorageError(StorageErrorCode.KEY_INVALID)
        return key

    def _key(self, version: int) -> StorageKey:
        if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
            raise StorageError(StorageErrorCode.KEY_VERSION_INVALID)
        try:
            key = self._key_provider.get_key(version)
        except StorageError:
            raise
        except Exception:
            raise StorageError(StorageErrorCode.KEY_UNAVAILABLE) from None
        if type(key) is not StorageKey:
            raise StorageError(StorageErrorCode.KEY_INVALID)
        if key.version != version:
            raise StorageError(StorageErrorCode.KEY_VERSION_INVALID)
        return key

    def _managed_path(self, artifact_id: EntityId) -> _ManagedPath:
        uuid_value = artifact_id.value
        uuid_hex = uuid_value.hex
        directory = self._root / "objects" / uuid_hex[:2] / uuid_hex[2:4]
        return _ManagedPath(directory / f"{uuid_value}.diosobj", directory)

    def _validate_publish_inputs(
        self,
        artifact_id: EntityId,
        artifact_kind: ArtifactKind,
        plaintext: bytes,
        created_at: datetime,
    ) -> StorageKey:
        if type(artifact_id) is not EntityId:
            raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
        if type(artifact_kind) is not ArtifactKind:
            raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
        if type(plaintext) is not bytes:
            raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
        if type(created_at) is not datetime:
            raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
        return self._current_key()

    def _ensure_managed_directory(self, directory: Path) -> None:
        objects = self._root / "objects"
        if not _is_safe_existing_directory(objects):
            raise StorageError(StorageErrorCode.ROOT_INVALID)
        first = directory.parent
        for component in (first, directory):
            if component.exists() and not _is_safe_existing_directory(component):
                raise StorageError(StorageErrorCode.ROOT_INVALID)
            if not component.exists():
                try:
                    self._fs.create_directory(component)
                except OSError:
                    raise StorageError(StorageErrorCode.ROOT_INVALID) from None
            if not _is_safe_existing_directory(component):
                raise StorageError(StorageErrorCode.ROOT_INVALID)

    def publish_bytes(
        self,
        *,
        artifact_id: EntityId,
        artifact_kind: ArtifactKind,
        plaintext: bytes,
        created_at: datetime,
    ) -> StoredArtifactRecord:
        key = self._validate_publish_inputs(artifact_id, artifact_kind, plaintext, created_at)
        managed_path = self._managed_path(artifact_id)
        envelope = build_envelope(
            key=key,
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            plaintext=plaintext,
        )
        ciphertext_sha256 = sha256_hex(envelope)
        self._ensure_managed_directory(managed_path.directory)
        if managed_path.final.exists():
            raise StorageError(StorageErrorCode.ARTIFACT_EXISTS)
        temporary = managed_path.directory / f".tmp-{uuid.uuid4()}.diosobj"
        fd: int | None = None
        try:
            fd = self._fs.open_exclusive_no_follow(temporary)
            self._fs.write_all(fd, envelope)
            self._fs.fsync_file(fd)
            self._fs.close(fd)
            fd = None
        except OSError:
            if fd is not None:
                with suppress(OSError):
                    self._fs.close(fd)
            self._unlink_if_safe_temporary(temporary)
            raise StorageError(StorageErrorCode.TEMP_WRITE_FAILED) from None

        try:
            self._fs.publish_no_replace(temporary, managed_path.final)
        except FileExistsError:
            self._unlink_if_safe_temporary(temporary)
            raise StorageError(StorageErrorCode.ARTIFACT_EXISTS) from None
        except OSError:
            self._unlink_if_safe_temporary(temporary)
            raise StorageError(StorageErrorCode.ATOMIC_PUBLISH_FAILED) from None

        if not _is_safe_regular_file(managed_path.final):
            raise StorageError(StorageErrorCode.ATOMIC_PUBLISH_FAILED)
        try:
            self._fs.fsync_directory(managed_path.directory)
        except OSError:
            raise StorageError(StorageErrorCode.IO_FAILED) from None
        return StoredArtifactRecord(
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            object_generation=1,
            plaintext_length=len(plaintext),
            plaintext_sha256=sha256_hex(plaintext),
            ciphertext_sha256=ciphertext_sha256,
            key_version=key.version,
            storage_format_version=FORMAT_VERSION,
            created_at=created_at,
        )

    def _read_envelope(self, expected: StoredArtifactRecord) -> bytes:
        managed_path = self._managed_path(expected.artifact_id)
        if not managed_path.final.exists():
            raise StorageError(StorageErrorCode.OBJECT_MISSING)
        if not _is_safe_regular_file(managed_path.final):
            raise StorageError(StorageErrorCode.IO_FAILED)
        try:
            data = self._fs.read_bytes_no_follow(managed_path.final)
        except StorageError:
            raise
        except OSError:
            raise StorageError(StorageErrorCode.IO_FAILED) from None
        if sha256_hex(data) != expected.ciphertext_sha256:
            raise StorageError(StorageErrorCode.EXPECTED_STATE_MISMATCH)
        return data

    def read_bytes(self, *, expected: StoredArtifactRecord) -> bytes:
        if type(expected) is not StoredArtifactRecord:
            raise StorageError(StorageErrorCode.EXPECTED_STATE_MISMATCH)
        data = self._read_envelope(expected)
        parsed = parse_envelope(data)
        header = parsed.header
        if (
            header["artifact_id"] != str(expected.artifact_id)
            or header["artifact_kind"] != expected.artifact_kind.value
            or header["object_generation"] != expected.object_generation
            or header["plaintext_length"] != expected.plaintext_length
            or header["plaintext_sha256"] != expected.plaintext_sha256
            or header["key_version"] != expected.key_version
            or header["format_version"] != expected.storage_format_version
        ):
            raise StorageError(StorageErrorCode.CONTEXT_MISMATCH)
        plaintext, _ = decrypt_envelope(key=self._key(expected.key_version), serialized=data)
        return plaintext

    def verify(self, *, expected: StoredArtifactRecord) -> None:
        self.read_bytes(expected=expected)

    def reconcile(
        self,
        *,
        expected: tuple[StoredArtifactRecord, ...],
    ) -> StorageReconciliationReport:
        expected_by_id = {str(record.artifact_id): record for record in expected}
        healthy: list[StorageReconciliationItem] = []
        missing: list[StorageReconciliationItem] = []
        invalid: list[StorageReconciliationItem] = []
        orphan: list[StorageReconciliationItem] = []
        temporary: list[StorageReconciliationItem] = []

        for record in expected:
            try:
                self.verify(expected=record)
            except StorageError as error:
                item = StorageReconciliationItem(
                    status=StorageReconciliationStatus.MISSING
                    if error.code is StorageErrorCode.OBJECT_MISSING
                    else StorageReconciliationStatus.INVALID,
                    artifact_id=record.artifact_id,
                    code=error.code.value,
                )
                if error.code is StorageErrorCode.OBJECT_MISSING:
                    missing.append(item)
                else:
                    invalid.append(item)
            else:
                healthy.append(
                    StorageReconciliationItem(
                        status=StorageReconciliationStatus.HEALTHY,
                        artifact_id=record.artifact_id,
                        code="OK",
                    )
                )

        seen_artifact_ids: set[EntityId] = set()
        objects = self._root / "objects"
        if objects.exists() and not _is_safe_existing_directory(objects):
            raise StorageError(StorageErrorCode.ROOT_INVALID)
        if _is_safe_existing_directory(objects):
            for path in self._iter_managed_entries(objects):
                if path.name.startswith(".tmp-"):
                    temporary.append(
                        StorageReconciliationItem(
                            status=StorageReconciliationStatus.TEMPORARY,
                            artifact_id=None,
                            code="TEMPORARY",
                        )
                    )
                    continue
                if not _FINAL_RE.fullmatch(path.name):
                    invalid.append(
                        StorageReconciliationItem(
                            status=StorageReconciliationStatus.INVALID,
                            artifact_id=None,
                            code=StorageErrorCode.ENVELOPE_FORMAT.value,
                        )
                    )
                    continue
                try:
                    data = self._fs.read_bytes_no_follow(path)
                    parsed = parse_envelope(data)
                    artifact_id = parsed.artifact_id
                    canonical = self._managed_path(artifact_id).final
                except (OSError, StorageError):
                    invalid.append(
                        StorageReconciliationItem(
                            status=StorageReconciliationStatus.INVALID,
                            artifact_id=None,
                            code=StorageErrorCode.ENVELOPE_FORMAT.value,
                        )
                    )
                    continue
                if path != canonical or artifact_id in seen_artifact_ids:
                    invalid.append(
                        StorageReconciliationItem(
                            status=StorageReconciliationStatus.INVALID,
                            artifact_id=artifact_id,
                            code=StorageErrorCode.CONTEXT_MISMATCH.value,
                        )
                    )
                    continue
                seen_artifact_ids.add(artifact_id)
                if str(artifact_id) not in expected_by_id:
                    orphan.append(
                        StorageReconciliationItem(
                            status=StorageReconciliationStatus.ORPHAN,
                            artifact_id=artifact_id,
                            code="ORPHAN",
                        )
                    )
        return StorageReconciliationReport(
            healthy=tuple(healthy),
            missing=tuple(missing),
            invalid=tuple(invalid),
            orphan=tuple(orphan),
            temporary=tuple(temporary),
        )

    def _iter_managed_entries(self, objects: Path) -> tuple[Path, ...]:
        entries: list[Path] = []
        try:
            first_level = tuple(objects.iterdir())
        except OSError:
            return ()
        for first in first_level:
            if not re.fullmatch(r"[0-9a-f]{2}", first.name):
                continue
            if not _is_safe_existing_directory(first):
                continue
            try:
                second_level = tuple(first.iterdir())
            except OSError:
                continue
            for second in second_level:
                if not re.fullmatch(r"[0-9a-f]{2}", second.name):
                    continue
                if not _is_safe_existing_directory(second):
                    continue
                try:
                    candidates = tuple(second.iterdir())
                except OSError:
                    continue
                for candidate in candidates:
                    if candidate.is_dir() or not _is_safe_regular_file(candidate):
                        continue
                    if candidate.name.endswith(".diosobj"):
                        entries.append(candidate)
        return tuple(entries)

    def cleanup_temporary_files(self) -> int:
        count = 0
        objects = self._root / "objects"
        if objects.exists() and not _is_safe_existing_directory(objects):
            raise StorageError(StorageErrorCode.TEMP_CLEANUP_FAILED)
        if not _is_safe_existing_directory(objects):
            return 0
        try:
            for path in self._iter_managed_entries(objects):
                if _TMP_RE.fullmatch(path.name) and _is_safe_regular_file(path):
                    self._fs.unlink(path)
                    count += 1
        except OSError:
            raise StorageError(StorageErrorCode.TEMP_CLEANUP_FAILED) from None
        return count

    def _unlink_if_safe_temporary(self, path: Path) -> None:
        if _TMP_RE.fullmatch(path.name) and _is_safe_regular_file(path):
            with suppress(OSError):
                self._fs.unlink(path)


__all__ = [
    "FilesystemFailurePoint",
    "ImmutableFilesystemStorage",
    "_FailingFilesystemOperations",
    "is_windows_reparse_point",
]
