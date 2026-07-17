from __future__ import annotations

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


def run_staged_sequence(
    directory: Path, failure: FailurePoint
) -> tuple[ExpectedRecord, Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    record = ExpectedRecord("PENDING", "object.bin", "digest-0001")
    temp_path = directory / "object.bin.tmp"
    final_path = directory / record.object_name
    encrypted_bytes = b"encrypted-synthetic-object"
    if failure is FailurePoint.BEFORE_TEMP_WRITE:
        return record, temp_path, final_path
    if failure is FailurePoint.DURING_TEMP_WRITE:
        temp_path.write_bytes(encrypted_bytes[:5])
        return record, temp_path, final_path
    _fsync_file(temp_path, encrypted_bytes)
    if failure is FailurePoint.AFTER_TEMP_WRITE:
        return record, temp_path, final_path
    os.replace(temp_path, final_path)
    if failure in {FailurePoint.AFTER_REPLACE, FailurePoint.BEFORE_ACTIVE_FINALIZATION}:
        return record, temp_path, final_path
    active = replace(record, state="ACTIVE")
    return active, temp_path, final_path


def reconcile(record: ExpectedRecord | None, final_path: Path, temp_path: Path) -> ReconcileStatus:
    if record is None:
        return ReconcileStatus.QUARANTINED if final_path.exists() else ReconcileStatus.SAFE_TO_RETRY
    if record.state == "ACTIVE" and final_path.exists() and not temp_path.exists():
        return ReconcileStatus.ACTIVE
    if record.state == "PENDING" and not final_path.exists():
        return ReconcileStatus.SAFE_TO_RETRY
    if record.state == "PENDING" and final_path.exists():
        return ReconcileStatus.QUARANTINED
    return ReconcileStatus.QUARANTINED


def windows_directory_fsync_limitation() -> str:
    return "WINDOWS_DIRECTORY_FSYNC_NOT_PORTABLE_IN_PYTHON_SPIKE"
