from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from spikes.windows_encryption.run import build_report
from spikes.windows_encryption.safe_report import (
    PackageEvidence,
    ReportCheck,
    ResultStatus,
    SafeReport,
    report_to_json,
    validate_report_file,
)

# Known synthetic values that probes would inject for privacy testing.
_SYNTHETIC_KEY = os.urandom(32)
_SYNTHETIC_MARKER = b"synthetic-privacy-test-marker-001"
_SYNTHETIC_NONCE = os.urandom(12)
_SYNTHETIC_BLOB_FRAGMENT = os.urandom(16)
_SYNTHETIC_TEMP_PREFIX = "pr-s001-test-tmp"


def test_safe_report_allowlist_blocks_unknown_fields_and_paths(tmp_path: Path) -> None:
    report = SafeReport(
        report_schema_version=1,
        timestamp_utc="2026-07-17T00:00:00+00:00",
        os_family="Windows",
        os_release="Server2022",
        architecture="AMD64",
        python_version="3.12",
        candidate_name="sqlcipher3-0.6.2",
        packages=[PackageEvidence("sqlcipher3", "0.6.2")],
        checks=[ReportCheck("dpapi", ResultStatus.PASS, "PASS")],
    )
    text = report_to_json(report)
    path = tmp_path / "safe.json"
    path.write_text(text, encoding="utf-8")
    validate_report_file(path)
    data = json.loads(text)
    data["absolute_path"] = str(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="ERR_REPORT_SCHEMA"):
        validate_report_file(bad)


def test_privacy_known_synthetic_values_absent_from_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify that specific synthetic values are absent from JSON, stdout, stderr."""
    report = build_report(tmp_path)
    text = report_to_json(report)
    captured = capsys.readouterr()
    combined = text + captured.out + captured.err

    assert _SYNTHETIC_KEY.hex() not in combined
    assert _SYNTHETIC_MARKER.decode() not in combined
    assert _SYNTHETIC_NONCE.hex() not in combined
    assert _SYNTHETIC_BLOB_FRAGMENT.hex() not in combined
    assert _SYNTHETIC_TEMP_PREFIX not in combined
    assert str(tmp_path) not in combined
    assert "Traceback" not in combined
    assert "BEGIN PRIVATE" not in combined


def test_timestamp_is_parseable_utc() -> None:
    """Verify the report timestamp is a valid UTC ISO timestamp."""
    report = SafeReport(
        report_schema_version=1,
        timestamp_utc="2026-07-17T12:00:00+00:00",
        os_family="Linux",
        os_release="6.8",
        architecture="x86_64",
        python_version="3.12",
        candidate_name="sqlcipher3-0.6.2",
    )
    text = report_to_json(report)
    assert "2026-07-17T12:00:00+00:00" in text


def test_invalid_timestamp_rejected() -> None:
    """Bad timestamp should fail validation."""
    data = {
        "architecture": "x86_64",
        "candidate_name": "sqlcipher3-0.6.2",
        "checks": [],
        "documented_limitations": [],
        "licensing_classifications": [],
        "os_family": "Linux",
        "os_release": "6.8",
        "packages": [],
        "python_version": "3.12",
        "recommendation": "CONDITIONALLY_FEASIBLE",
        "report_schema_version": 1,
        "sqlcipher_version": "UNSUPPORTED",
        "sqlite_version": "UNSUPPORTED",
        "timestamp_utc": "not-a-timestamp",
        "wheels": [],
        "windows_11_x64_result": "NOT_DEMONSTRATED",
    }
    with pytest.raises(ValueError, match="ERR_REPORT_TIMESTAMP"):
        from spikes.windows_encryption.safe_report import validate_report_object

        validate_report_object(data)


def test_negative_duration_rejected() -> None:
    """Negative duration should fail validation."""
    check: dict[str, object] = {
        "byte_size": 0,
        "duration_ms": -1,
        "identifier": "test",
        "reason_code": "PASS",
        "status": "PASS",
    }
    with pytest.raises(ValueError, match="ERR_REPORT_SCHEMA"):
        from spikes.windows_encryption.safe_report import _validate_check

        _validate_check(check)


def test_negative_size_rejected() -> None:
    """Negative byte_size should fail validation."""
    check: dict[str, object] = {
        "byte_size": -5,
        "duration_ms": 0,
        "identifier": "test",
        "reason_code": "PASS",
        "status": "PASS",
    }
    with pytest.raises(ValueError, match="ERR_REPORT_SCHEMA"):
        from spikes.windows_encryption.safe_report import _validate_check

        _validate_check(check)


def test_status_reason_consistency() -> None:
    """PASS status with FAIL reason should be rejected."""
    data = {
        "architecture": "x86_64",
        "candidate_name": "sqlcipher3-0.6.2",
        "checks": [
            {
                "byte_size": 0,
                "duration_ms": 0,
                "identifier": "inconsistent",
                "reason_code": "FAIL",
                "status": "PASS",
            }
        ],
        "documented_limitations": [],
        "licensing_classifications": [],
        "os_family": "Linux",
        "os_release": "6.8",
        "packages": [],
        "python_version": "3.12",
        "recommendation": "NOT_FEASIBLE",
        "report_schema_version": 1,
        "sqlcipher_version": "UNSUPPORTED",
        "sqlite_version": "UNSUPPORTED",
        "timestamp_utc": "2026-07-17T12:00:00+00:00",
        "wheels": [],
        "windows_11_x64_result": "NOT_DEMONSTRATED",
    }
    with pytest.raises(ValueError, match="ERR_REPORT_REASON"):
        from spikes.windows_encryption.safe_report import validate_report_object

        validate_report_object(data)
