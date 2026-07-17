from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

FORBIDDEN_KEYS = {"key", "nonce", "ciphertext", "plaintext", "blob", "username", "hostname", "path", "environment", "exception", "stack"}


class ResultStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"


@dataclass(frozen=True)
class ReportCheck:
    identifier: str
    status: ResultStatus
    reason_code: str
    duration_ms: int = 0
    byte_size: int = 0


@dataclass(frozen=True)
class SafeReport:
    report_schema_version: int
    timestamp_utc: str
    os_family: str
    os_release: str
    architecture: str
    python_version: str
    candidate_name: str
    package_versions: dict[str, str] = field(default_factory=dict)
    sqlcipher_version: str = "NOT_DEMONSTRATED"
    sqlite_version: str = "NOT_DEMONSTRATED"
    checks: list[ReportCheck] = field(default_factory=list)
    wheel_hashes: dict[str, str] = field(default_factory=dict)
    licensing_classifications: dict[str, str] = field(default_factory=dict)
    documented_limitations: list[str] = field(default_factory=list)


def new_report(os_family: str, os_release: str, architecture: str, python_version: str, candidate_name: str) -> SafeReport:
    return SafeReport(1, datetime.now(UTC).isoformat(), os_family, os_release, architecture, python_version, candidate_name)


def _validate_obj(obj: object) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            lowered = str(key).lower()
            if any(token in lowered for token in FORBIDDEN_KEYS):
                raise ValueError("ERR_REPORT_FIELD_NOT_ALLOWLISTED")
            _validate_obj(value)
    elif isinstance(obj, list):
        for value in obj:
            _validate_obj(value)
    elif isinstance(obj, str):
        if "/" in obj or "\\" in obj or len(obj) > 512:
            raise ValueError("ERR_REPORT_VALUE_NOT_ALLOWLISTED")


def report_to_json(report: SafeReport) -> str:
    obj = asdict(report)
    _validate_obj(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def write_report(report: SafeReport, output: Path) -> None:
    output.write_text(report_to_json(report), encoding="utf-8")


def validate_report_file(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_obj(data)
