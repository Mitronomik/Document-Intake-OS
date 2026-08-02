"""Sanitized Windows production-SQLCipher verifier for PR-012."""

from __future__ import annotations

import importlib
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from scripts.pr012_regions_verifier_support import VerifierEvidence

from document_intake.persistence import database
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations.v0008_document_regions import MIGRATION

support = importlib.import_module(
    "scripts.pr012_regions_verifier_support" if __package__ else "pr012_regions_verifier_support"
)

_LABELS = (
    "PR012_VERIFY schema_version=9",
    f"PR012_VERIFY candidate_v0008_checksum={MIGRATION.checksum}",
    "PR012_VERIFY populated_encrypted_v7_to_v8=PASS",
    "PR012_VERIFY source_a_history=PASS",
    "PR012_VERIFY source_b_isolation=PASS",
    "PR012_VERIFY prepared_references=PASS",
    "PR012_VERIFY repository_reopen=PASS",
    "PR012_VERIFY second_lineage_service=PASS",
    "PR012_VERIFY second_lineage_revision=PASS",
    "PR012_VERIFY region_set_history=PASS",
    "PR012_VERIFY audit_order=PASS",
    "PR012_VERIFY migration_history=PASS",
    "PR012_VERIFY foreign_keys=PASS",
    "PR012_VERIFY cipher_integrity=PASS",
    "PR012_VERIFY wrong_key_rejection=PASS",
    "PR012_VERIFY sqlite_rejected=PASS",
    "PR012_VERIFY privacy=PASS",
    "PR012_VERIFY result=PASS",
)
_UNSUPPORTED = ("PR012_VERIFY result=INCONCLUSIVE code=UNSUPPORTED_PLATFORM",)
_PROBE_PATH = "DOCUMENT_INTAKE_PR012_PROBE_PATH"
_PROBE_KEY = "DOCUMENT_INTAKE_PR012_PROBE_KEY"
_PRIVACY_FORBIDDEN = (
    "/tmp/",
    "/private/",
    "C:\\",
    "\\Users\\",
    "00000000-",
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "PRAGMA key",
    "key=",
    "verify-a.png",
    "synthetic-image-marker",
    "coordinate-marker",
    "raw-exception-marker",
)


class _Key:
    def __init__(self, value: bytes = b"R" * 32) -> None:
        self.value = value

    def get_database_key(self) -> bytes:
        return self.value


def _unsupported_code() -> str | None:
    return (
        None
        if platform.system() == "Windows" and platform.machine() == "AMD64"
        else "UNSUPPORTED_PLATFORM"
    )


def _emit(lines: tuple[str, ...]) -> None:
    for line in lines:
        print(line)


def _wrong_key_probe() -> int | None:
    raw_path = os.environ.get(_PROBE_PATH)
    raw_key = os.environ.get(_PROBE_KEY)
    if raw_path is None and raw_key is None:
        return None
    if raw_path is None or raw_key is None:
        return 2
    try:
        connection = database._open_connection(Path(raw_path), _Key(bytes.fromhex(raw_key)))
    except PersistenceError as error:
        return 0 if error.code is PersistenceErrorCode.DB_KEY_REJECTED else 2
    except Exception:
        return 2
    connection.close()
    return 1


def _wrong_key_rejected(path: Path) -> bool:
    environment = os.environ.copy()
    environment[_PROBE_PATH] = str(path)
    environment[_PROBE_KEY] = (b"W" * 32).hex()
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=60,
    )
    return completed.returncode == 0


def _run_supported(root: Path | None = None) -> VerifierEvidence:
    if root is not None:
        return cast(
            "VerifierEvidence",
            support.run_populated_verification(root, _wrong_key_rejected),
        )
    with tempfile.TemporaryDirectory(prefix="pr012-verify-") as temporary:
        return cast(
            "VerifierEvidence",
            support.run_populated_verification(Path(temporary), _wrong_key_rejected),
        )


def main() -> int:
    if _unsupported_code() is not None:
        _emit(_UNSUPPORTED)
        return 2
    try:
        evidence = _run_supported()
    except Exception:
        evidence = None
    if evidence is None or not all(
        type(getattr(evidence, field)) is bool and getattr(evidence, field)
        for field in support.EVIDENCE_FIELDS
    ):
        print("PR012_VERIFY result=FAIL")
        return 1
    _emit(_LABELS)
    return 0


if __name__ == "__main__":
    probe_result = _wrong_key_probe()
    raise SystemExit(main() if probe_result is None else probe_result)
