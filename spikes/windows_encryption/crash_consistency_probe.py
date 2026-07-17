from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path


class ReconcileStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SAFE_TO_RETRY = "SAFE_TO_RETRY"
    QUARANTINED = "QUARANTINED"


class FailurePoint(StrEnum):
    NONE = "none"
    BEFORE_TEMP_WRITE = "before-temporary-write"
    DURING_TEMP_WRITE = "during-temporary-write"
    AFTER_TEMP_WRITE = "after-temporary-write"
    AFTER_REPLACE = "after-replace"
    BEFORE_ACTIVE_FINALIZATION = "before-active-finalization"
    AFTER_ACTIVE_FINALIZATION = "after-active-finalization"


@dataclass(frozen=True)
class ExpectedRecord:
    state: str
    object_name: str
    digest: str


def _fsync_file(path: Path, data: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _digest_for(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_staged_sequence(
    directory: Path, failure: FailurePoint
) -> tuple[ExpectedRecord, Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    object_data = b"opaque synthetic bytes for crash consistency test"
    digest = _digest_for(object_data)
    record = ExpectedRecord("PENDING", "object.bin", digest)
    temp_path = directory / "object.bin.tmp"
    final_path = directory / record.object_name
    if failure is FailurePoint.BEFORE_TEMP_WRITE:
        return record, temp_path, final_path
    if failure is FailurePoint.DURING_TEMP_WRITE:
        temp_path.write_bytes(object_data[:5])
        return record, temp_path, final_path
    _fsync_file(temp_path, object_data)
    if failure is FailurePoint.AFTER_TEMP_WRITE:
        return record, temp_path, final_path
    os.replace(temp_path, final_path)
    if failure in {FailurePoint.AFTER_REPLACE, FailurePoint.BEFORE_ACTIVE_FINALIZATION}:
        return record, temp_path, final_path
    active = replace(record, state="ACTIVE")
    return active, temp_path, final_path


def reconcile(record: ExpectedRecord | None, final_path: Path, temp_path: Path) -> ReconcileStatus:
    if record is None:
        if final_path.exists():
            return ReconcileStatus.QUARANTINED
        return ReconcileStatus.SAFE_TO_RETRY
    if record.state == "ACTIVE":
        if not final_path.exists():
            return ReconcileStatus.QUARANTINED
        actual_digest = _digest_for(final_path.read_bytes())
        if actual_digest == record.digest:
            return ReconcileStatus.ACTIVE
        return ReconcileStatus.QUARANTINED
    if record.state == "PENDING":
        if final_path.exists():
            return ReconcileStatus.QUARANTINED
        if temp_path.exists():
            temp_size = temp_path.stat().st_size
            expected_size = len(b"opaque synthetic bytes for crash consistency test")
            if temp_size == expected_size:
                return ReconcileStatus.SAFE_TO_RETRY
            if temp_size < expected_size:
                return ReconcileStatus.SAFE_TO_RETRY
        return ReconcileStatus.SAFE_TO_RETRY
    return ReconcileStatus.QUARANTINED


def windows_directory_fsync_limitation() -> str:
    return "WINDOWS_DIRECTORY_FSYNC_NOT_PORTABLE_IN_PYTHON_SPIKE"
