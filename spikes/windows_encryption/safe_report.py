from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class ResultStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"


ALLOWED_REASON_CODES = frozenset(
    {
        "PASS",
        "FAIL",
        "UNSUPPORTED_NON_WINDOWS",
        "UNSUPPORTED_DEPENDENCY_MISSING",
        "NOT_DEMONSTRATED",
        "NOT_DEMONSTRATED_WINDOWS11",
        "ERR_SQLCIPHER_IMPORT",
        "ERR_DPAPI_PROTECT_FAILED",
        "ERR_DPAPI_UNPROTECT_FAILED",
        "ERR_DPAPI_ARTIFACT_INVALID",
        "ERR_DPAPI_CURRENT_PROCESS_VERIFY_FAILED",
        "ERR_DPAPI_SUBPROCESS_KEY_MISMATCH",
        "ERR_DPAPI_SUBPROCESS_VERIFY_FAILED",
        "ERR_ACL_PROBE_FAILED",
        "ERR_ACL_CURRENT_USER_RIGHTS",
        "ERR_ACL_SYSTEM_RIGHTS",
        "ERR_ACL_ADMINISTRATORS_RIGHTS",
        "ERR_ACL_BROAD_WRITE",
        "ERR_ACL_CLEANUP_FAILED",
        "ERR_REPORT_UNSAFE",
        "ERR_SPIKE_EXCEPTION",
        "ERR_OFFLINE_SMOKE",
        "ERR_CRASH_MODEL",
        "ERR_ENVELOPE_AUTH_FAILED",
        "ERR_ROLLBACK_UNDETECTED",
        "ERR_CLEANUP_FAILED",
        "ERR_CORRECT_KEY_MARKER_MISMATCH",
        "ERR_CORRECT_KEY_EXCEPTION",
        "ERR_WRONG_KEY_ACCEPTED",
        "ERR_SQLITE_ACCEPTED",
        "ERR_BIT_TAMPER_UNDETECTED",
        "ERR_TRUNCATION_UNDETECTED",
        "ERR_PLAINTEXT_HEADER",
        "ERR_MARKER_IN_DB",
        "ERR_TEMP_STORE_NOT_MEMORY",
        "ERR_MARKER_IN_WAL",
        "ERR_MARKER_IN_JOURNAL",
        "ERR_MARKER_IN_TEMP",
        "ERR_PLAINTEXT_WAL",
        "ERR_CIPHER_STATUS_INACTIVE",
        "ERR_CIPHER_INTEGRITY_FAILED",
        "ERR_ENCRYPTED_DB_NOT_CREATED",
    }
)


@dataclass(frozen=True)
class ReportCheck:
    identifier: str
    status: ResultStatus
    reason_code: str
    duration_ms: int = 0
    byte_size: int = 0


@dataclass(frozen=True)
class PackageEvidence:
    name: str
    version: str


@dataclass(frozen=True)
class WheelEvidence:
    filename: str
    tag: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SafeReport:
    report_schema_version: int
    timestamp_utc: str
    os_family: str
    os_release: str
    architecture: str
    python_version: str
    candidate_name: str
    packages: list[PackageEvidence] = field(default_factory=list)
    sqlcipher_version: str = "UNSUPPORTED"
    sqlite_version: str = "UNSUPPORTED"
    checks: list[ReportCheck] = field(default_factory=list)
    wheels: list[WheelEvidence] = field(default_factory=list)
    licensing_classifications: list[str] = field(default_factory=list)
    documented_limitations: list[str] = field(default_factory=list)
    recommendation: str = "CONDITIONALLY_FEASIBLE"
    windows_11_x64_result: ResultStatus = ResultStatus.NOT_DEMONSTRATED


_ALLOWED_TOP_LEVEL = {
    "architecture",
    "candidate_name",
    "checks",
    "documented_limitations",
    "licensing_classifications",
    "os_family",
    "os_release",
    "packages",
    "python_version",
    "recommendation",
    "report_schema_version",
    "sqlcipher_version",
    "sqlite_version",
    "timestamp_utc",
    "wheels",
    "windows_11_x64_result",
}
_ALLOWED_CHECK = {"byte_size", "duration_ms", "identifier", "reason_code", "status"}
_ALLOWED_PACKAGE = {"name", "version"}
_ALLOWED_WHEEL = {"filename", "sha256", "size_bytes", "tag"}
_ALLOWED_RECOMMENDATIONS = {"FEASIBLE", "CONDITIONALLY_FEASIBLE", "NOT_FEASIBLE"}


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _safe_string(value: str) -> bool:
    if len(value) > 256 or "/" in value or "\\\\" in value:
        return False
    forbidden = ("BEGIN", "PRIVATE", "Traceback", "nonce", "ciphertext", "plaintext")
    return not any(token.lower() in value.lower() for token in forbidden)


def _validate_check(check: dict[str, Any]) -> None:
    if set(check) != _ALLOWED_CHECK:
        raise ValueError("ERR_REPORT_SCHEMA")
    if check["status"] not in ResultStatus._value2member_map_:
        raise ValueError("ERR_REPORT_STATUS")
    if check["reason_code"] not in ALLOWED_REASON_CODES:
        raise ValueError("ERR_REPORT_REASON")
    if not _safe_string(check["identifier"]):
        raise ValueError("ERR_REPORT_UNSAFE")
    if not isinstance(check.get("duration_ms", 0), int) or check["duration_ms"] < 0:
        raise ValueError("ERR_REPORT_SCHEMA")
    if not isinstance(check.get("byte_size", 0), int) or check["byte_size"] < 0:
        raise ValueError("ERR_REPORT_SCHEMA")


def _validate_package(package: dict[str, Any]) -> None:
    if set(package) != _ALLOWED_PACKAGE:
        raise ValueError("ERR_REPORT_SCHEMA")
    if not _safe_string(package["name"]) or not _safe_string(package["version"]):
        raise ValueError("ERR_REPORT_UNSAFE")


def _validate_wheel(wheel: dict[str, Any]) -> None:
    if set(wheel) != _ALLOWED_WHEEL:
        raise ValueError("ERR_REPORT_SCHEMA")
    if not _safe_string(wheel["filename"]) or not _safe_string(wheel["tag"]):
        raise ValueError("ERR_REPORT_UNSAFE")
    if len(wheel["sha256"]) != 64 or not all(
        char in "0123456789abcdef" for char in wheel["sha256"]
    ):
        raise ValueError("ERR_REPORT_UNSAFE")
    if not isinstance(wheel.get("size_bytes", 0), int) or wheel["size_bytes"] < 0:
        raise ValueError("ERR_REPORT_SCHEMA")


def _validate_timestamp(value: str) -> None:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("ERR_REPORT_TIMESTAMP") from None


def validate_report_object(data: dict[str, Any]) -> None:
    if set(data) != _ALLOWED_TOP_LEVEL:
        raise ValueError("ERR_REPORT_SCHEMA")
    if data["recommendation"] not in _ALLOWED_RECOMMENDATIONS:
        raise ValueError("ERR_REPORT_RECOMMENDATION")
    if not isinstance(data["report_schema_version"], int) or data["report_schema_version"] <= 0:
        raise ValueError("ERR_REPORT_SCHEMA")
    _validate_timestamp(str(data.get("timestamp_utc", "")))
    if data["windows_11_x64_result"] not in ResultStatus._value2member_map_:
        raise ValueError("ERR_REPORT_STATUS")
    for key in ("os_family", "os_release", "architecture", "python_version", "candidate_name"):
        if not _safe_string(str(data[key])):
            raise ValueError("ERR_REPORT_UNSAFE")
    if not _safe_string(data["sqlcipher_version"]) or not _safe_string(data["sqlite_version"]):
        raise ValueError("ERR_REPORT_UNSAFE")
    for check in data["checks"]:
        _validate_check(check)
    for package in data["packages"]:
        _validate_package(package)
    for wheel in data["wheels"]:
        _validate_wheel(wheel)
    for value in data["licensing_classifications"] + data["documented_limitations"]:
        if not _safe_string(str(value)):
            raise ValueError("ERR_REPORT_UNSAFE")
    for check in data["checks"]:
        status_val = check["status"]
        reason_val = check["reason_code"]
        if status_val == "PASS" and reason_val not in ("PASS",):
            raise ValueError("ERR_REPORT_REASON")
        if status_val == "FAIL" and reason_val == "PASS":
            raise ValueError("ERR_REPORT_REASON")


def report_to_json(report: SafeReport) -> str:
    data = asdict(report)
    validate_report_object(data)
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def write_report(report: SafeReport, output: Path) -> None:
    output.write_text(report_to_json(report), encoding="utf-8")


def validate_report_file(path: Path) -> None:
    validate_report_object(json.loads(path.read_text(encoding="utf-8")))
