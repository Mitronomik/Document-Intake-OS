"""Synthetic manual verification for PR-006 storage."""

from __future__ import annotations

import getpass
import platform
import socket
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cryptography

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.storage import StorageKey
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId
from document_intake.persistence.migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS
from document_intake.persistence.migrations.model import migration_checksum
from document_intake.persistence.migrations.v0002_stored_artifacts import CHECKSUM, STATEMENTS
from document_intake.storage.envelope import ALGORITHM, FORMAT_VERSION, build_envelope, sha256_hex
from document_intake.storage.errors import StorageError, StorageErrorCode
from document_intake.storage.filesystem import ImmutableFilesystemStorage

_SYNTHETIC_MARKER = b"synthetic-pr006-marker"
_EXPECTED_V0002_CHECKSUM = "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d"


class _KeyProvider:
    def __init__(self, key: bytes) -> None:
        self._key = key

    def get_current_key(self) -> StorageKey:
        return StorageKey(1, self._key)

    def get_key(self, version: int) -> StorageKey:
        return StorageKey(version, self._key)


def _expect_storage_error(
    function: object,
    code: StorageErrorCode,
    captured: list[str],
) -> bool:
    if not callable(function):
        return False
    try:
        function()
    except StorageError as error:
        captured.extend((str(error), repr(error)))
        return error.code is code and str(error) == code.value and repr(error) == code.value
    return False


def _object_path(root: Path, record: StoredArtifactRecord) -> Path:
    uuid_hex = record.artifact_id.value.hex
    return root / "objects" / uuid_hex[:2] / uuid_hex[2:4] / f"{record.artifact_id}.diosobj"


def run_checks() -> dict[str, str]:
    statuses: dict[str, str] = {}
    captured_public_diagnostics: list[str] = []
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        key = b"M" * 32
        storage = ImmutableFilesystemStorage(root, _KeyProvider(key))
        artifact_id = EntityId(uuid4())
        record = storage.publish_bytes(
            artifact_id=artifact_id,
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=_SYNTHETIC_MARKER,
            created_at=datetime.now(UTC),
        )
        statuses["publish"] = "PASS"
        statuses["exact_read"] = (
            "PASS" if storage.read_bytes(expected=record) == _SYNTHETIC_MARKER else "FAIL"
        )

        wrong_key_storage = ImmutableFilesystemStorage(root, _KeyProvider(b"W" * 32))
        statuses["wrong_key"] = (
            "PASS"
            if _expect_storage_error(
                lambda: wrong_key_storage.read_bytes(expected=record),
                StorageErrorCode.AUTH_FAILED,
                captured_public_diagnostics,
            )
            else "FAIL"
        )

        object_path = _object_path(root, record)
        original_envelope = object_path.read_bytes()
        object_path.write_bytes(original_envelope[:-1] + bytes([original_envelope[-1] ^ 1]))
        statuses["tamper"] = (
            "PASS"
            if _expect_storage_error(
                lambda: storage.read_bytes(expected=record),
                StorageErrorCode.EXPECTED_STATE_MISMATCH,
                captured_public_diagnostics,
            )
            else "FAIL"
        )
        object_path.write_bytes(original_envelope)

        statuses["duplicate_publication"] = (
            "PASS"
            if _expect_storage_error(
                lambda: storage.publish_bytes(
                    artifact_id=artifact_id,
                    artifact_kind=ArtifactKind.ORIGINAL,
                    plaintext=b"replacement",
                    created_at=datetime.now(UTC),
                ),
                StorageErrorCode.ARTIFACT_EXISTS,
                captured_public_diagnostics,
            )
            else "FAIL"
        )

        older_envelope = build_envelope(
            key=StorageKey(1, key),
            artifact_id=record.artifact_id,
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=b"older same id synthetic",
        )
        object_path.write_bytes(older_envelope)
        statuses["rollback"] = (
            "PASS"
            if sha256_hex(older_envelope) != record.ciphertext_sha256
            and _expect_storage_error(
                lambda: storage.read_bytes(expected=record),
                StorageErrorCode.EXPECTED_STATE_MISMATCH,
                captured_public_diagnostics,
            )
            else "FAIL"
        )
        object_path.write_bytes(original_envelope)

        orphan_record = storage.publish_bytes(
            artifact_id=EntityId(uuid4()),
            artifact_kind=ArtifactKind.ORIGINAL,
            plaintext=b"orphan synthetic",
            created_at=datetime.now(UTC),
        )
        report = storage.reconcile(expected=(record,))
        statuses["orphan_detection"] = "PASS" if report.counts["orphan"] == 1 else "FAIL"
        captured_public_diagnostics.extend(
            [
                repr(report),
                *(repr(item) for group in (report.healthy, report.orphan) for item in group),
            ]
        )

        temp = object_path.parent / ".tmp-00000000-0000-0000-0000-000000000000.diosobj"
        temp.write_bytes(original_envelope)
        statuses["temp_cleanup"] = (
            "PASS" if storage.cleanup_temporary_files() == 1 and not temp.exists() else "FAIL"
        )
        statuses["plaintext_on_disk_scan"] = (
            "PASS"
            if all(
                _SYNTHETIC_MARKER not in path.read_bytes()
                for path in root.rglob("*")
                if path.is_file() and not path.is_symlink()
            )
            else "FAIL"
        )
        statuses["schema_version"] = "PASS" if CURRENT_SCHEMA_VERSION >= 2 else "FAIL"
        statuses["migration_v0002_present"] = (
            "PASS"
            if any(
                m.version == 2
                and m.name == "stored_artifacts_pr006"
                and m.checksum == _EXPECTED_V0002_CHECKSUM
                for m in MIGRATIONS
            )
            else "FAIL"
        )
        statuses["migration_v0002_checksum"] = (
            "PASS"
            if migration_checksum(STATEMENTS) == CHECKSUM == _EXPECTED_V0002_CHECKSUM
            else "FAIL"
        )
        provisional_report = format_report({**statuses, "sanitized_privacy": "PENDING"})
        forbidden_values = (
            str(root),
            str(object_path),
            str(artifact_id),
            str(orphan_record.artifact_id),
            key.decode("ascii"),
            _SYNTHETIC_MARKER.decode("ascii"),
            record.plaintext_sha256,
            record.ciphertext_sha256,
            sha256_hex(older_envelope),
            getpass.getuser(),
            socket.gethostname(),
            "Traceback",
            "InvalidTag",
            "No such file",
        )
        statuses["sanitized_privacy"] = (
            "PASS"
            if report_is_sanitized(
                "\n".join((provisional_report, *captured_public_diagnostics)),
                forbidden_values,
            )
            else "FAIL"
        )
    return statuses


def format_report(statuses: dict[str, str]) -> str:
    lines = [
        f"os_family={platform.system()} arch={platform.machine()}",
        f"python={platform.python_version()}",
        f"cryptography={cryptography.__version__}",
        f"storage_format_version={FORMAT_VERSION} algorithm={ALGORITHM}",
        f"schema_version={CURRENT_SCHEMA_VERSION} migration_v0002_checksum={CHECKSUM}",
    ]
    lines.extend(f"{key}={value}" for key, value in sorted(statuses.items()))
    return "\n".join(lines)


def report_is_sanitized(report: str, forbidden_values: tuple[str, ...]) -> bool:
    return all(value not in report for value in forbidden_values if value)


def main() -> int:
    statuses = run_checks()
    report = format_report(statuses)
    print(report)
    return 0 if all(value == "PASS" for value in statuses.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
