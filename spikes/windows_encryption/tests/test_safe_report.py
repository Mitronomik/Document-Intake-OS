from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from spikes.windows_encryption.run import build_report
from spikes.windows_encryption.safe_report import (
    ALLOWED_REASON_CODES,
    PackageEvidence,
    ReportCheck,
    ResultStatus,
    SafeReport,
    report_to_json,
    validate_report_file,
    validate_report_object,
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
        validate_report_object(data)


# ---------------------------------------------------------------------------
# New safe_report tests for sqlcipher reason codes
# ---------------------------------------------------------------------------


def test_synthetic_report_with_sqlcipher_checks_accepted() -> None:
    """Synthetic report containing cipher-status, cipher-integrity,
    encrypted-db-created with PASS/PASS should be accepted."""
    report = SafeReport(
        report_schema_version=1,
        timestamp_utc="2026-07-17T12:00:00+00:00",
        os_family="Windows",
        os_release="Server2022",
        architecture="AMD64",
        python_version="3.12",
        candidate_name="sqlcipher3-0.6.2",
        checks=[
            ReportCheck("cipher-status", ResultStatus.PASS, "PASS"),
            ReportCheck("cipher-integrity", ResultStatus.PASS, "PASS"),
            ReportCheck("encrypted-db-created", ResultStatus.PASS, "PASS"),
        ],
    )
    report_to_json(report)  # should not raise


def test_pass_status_with_fail_reason_rejected() -> None:
    """PASS status with FAIL reason (not 'PASS') should be rejected."""
    data = {
        "architecture": "x86_64",
        "candidate_name": "sqlcipher3-0.6.2",
        "checks": [
            {
                "byte_size": 0,
                "duration_ms": 0,
                "identifier": "bad",
                "reason_code": "ERR_CIPHER_STATUS_INACTIVE",
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
        validate_report_object(data)


def test_fail_status_with_pass_reason_rejected() -> None:
    """FAIL status with PASS reason should be rejected."""
    data = {
        "architecture": "x86_64",
        "candidate_name": "sqlcipher3-0.6.2",
        "checks": [
            {
                "byte_size": 0,
                "duration_ms": 0,
                "identifier": "bad",
                "reason_code": "PASS",
                "status": "FAIL",
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
        validate_report_object(data)


def test_pass_status_with_raw_value_rejected() -> None:
    """PASS status with raw PRAGMA value ('1') as reason should be rejected."""
    data = {
        "architecture": "x86_64",
        "candidate_name": "sqlcipher3-0.6.2",
        "checks": [
            {
                "byte_size": 0,
                "duration_ms": 0,
                "identifier": "cipher-status",
                "reason_code": "1",
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
        validate_report_object(data)


def test_new_reason_codes_are_allowlisted() -> None:
    """All new SQLCipher reason codes must be in ALLOWED_REASON_CODES."""
    new_codes = {
        "ERR_CIPHER_STATUS_INACTIVE",
        "ERR_CIPHER_INTEGRITY_FAILED",
        "ERR_ENCRYPTED_DB_NOT_CREATED",
    }
    assert new_codes <= ALLOWED_REASON_CODES


def test_acl_reason_codes_are_allowlisted() -> None:
    assert {
        "ERR_ACL_CURRENT_USER_RIGHTS",
        "ERR_ACL_SYSTEM_RIGHTS",
        "ERR_ACL_ADMINISTRATORS_RIGHTS",
        "ERR_ACL_BROAD_WRITE",
        "ERR_ACL_CLEANUP_FAILED",
        "ERR_ACL_PROBE_FAILED",
        "ERR_ACL_SID_LOOKUP",
        "ERR_ACL_APPLY_INHERITANCE",
        "ERR_ACL_APPLY_SYSTEM",
        "ERR_ACL_APPLY_ADMINISTRATORS",
        "ERR_ACL_APPLY_CURRENT_USER",
        "ERR_ACL_POWERSHELL_LAUNCH",
        "ERR_ACL_POWERSHELL_PROCESS",
        "ERR_ACL_READ",
        "ERR_ACL_NORMALIZE_TO_SID",
        "ERR_ACL_JSON_SERIALIZE",
        "ERR_ACL_JSON_PARSE",
        "ERR_ACL_RESULT_SHAPE",
        "ERR_ACL_UNEXPECTED",
    } <= ALLOWED_REASON_CODES


def test_safe_report_accepts_acl_identifiers_and_reasons() -> None:
    report = SafeReport(
        report_schema_version=1,
        timestamp_utc="2026-07-17T12:00:00+00:00",
        os_family="Windows",
        os_release="Server2022",
        architecture="AMD64",
        python_version="3.12",
        candidate_name="sqlcipher3-0.6.2",
        checks=[
            ReportCheck(
                "acl-current-user-rights",
                ResultStatus.FAIL,
                "ERR_ACL_CURRENT_USER_RIGHTS",
            ),
            ReportCheck("acl-system-rights", ResultStatus.FAIL, "ERR_ACL_SYSTEM_RIGHTS"),
            ReportCheck(
                "acl-administrators-rights",
                ResultStatus.FAIL,
                "ERR_ACL_ADMINISTRATORS_RIGHTS",
            ),
            ReportCheck("acl-broad-write-blocked", ResultStatus.FAIL, "ERR_ACL_BROAD_WRITE"),
            ReportCheck("acl-stage-current-user-sid", ResultStatus.PASS, "PASS"),
            ReportCheck("acl-stage-apply", ResultStatus.FAIL, "ERR_ACL_APPLY_SYSTEM"),
            ReportCheck("acl-stage-read", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"),
            ReportCheck(
                "acl-stage-normalize-to-sid", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"
            ),
            ReportCheck(
                "acl-stage-json-serialize", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"
            ),
            ReportCheck("acl-stage-json-parse", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"),
            ReportCheck("acl-directory-cleanup", ResultStatus.FAIL, "ERR_ACL_CLEANUP_FAILED"),
        ],
        recommendation="NOT_FEASIBLE",
    )
    assert "S-" not in report_to_json(report)


def test_pr_s001_f2_reason_codes_are_allowlisted() -> None:
    assert {
        "UNSUPPORTED_WAL_MODE",
        "UNSUPPORTED_ROLLBACK_JOURNAL_MODE",
        "ERR_WAL_NOT_CREATED",
        "ERR_WAL_EMPTY",
        "ERR_WAL_CONTROL_MARKER_MISSING",
        "ERR_WAL_PROBE_FAILED",
        "ERR_JOURNAL_NOT_CREATED",
        "ERR_JOURNAL_EMPTY",
        "ERR_JOURNAL_CONTROL_MARKER_MISSING",
        "ERR_JOURNAL_PROBE_FAILED",
        "ERR_MARKER_IN_WAL",
        "ERR_MARKER_IN_JOURNAL",
    } <= ALLOWED_REASON_CODES


def test_pr_s001_f2_safe_report_excludes_marker_path_and_exception(tmp_path: Path) -> None:
    report = SafeReport(
        report_schema_version=1,
        timestamp_utc="2026-07-17T12:00:00+00:00",
        os_family="Windows",
        os_release="Server2022",
        architecture="AMD64",
        python_version="3.12",
        candidate_name="sqlcipher3-0.6.2",
        checks=[
            ReportCheck(
                "wal-encrypted-content", ResultStatus.FAIL, "ERR_WAL_CONTROL_MARKER_MISSING"
            )
        ],
        recommendation="NOT_FEASIBLE",
    )
    text = report_to_json(report)
    assert "synthetic-record" not in text
    assert str(tmp_path) not in text
    assert "Traceback" not in text


def _passing_report_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    from spikes.windows_encryption import run
    from spikes.windows_encryption.acl_probe import AclProbeResult
    from spikes.windows_encryption.sqlcipher_probe import CheckResult, SqlcipherEvidence

    monkeypatch.setattr(
        run,
        "run_sqlcipher_probe",
        lambda path: SqlcipherEvidence(
            status="PASS",
            sqlcipher_version="4.5.0",
            sqlite_version="3.45.0",
            checks=(CheckResult("cipher-status", "PASS", "PASS"),),
        ),
    )
    monkeypatch.setattr(
        run,
        "run_acl_probe",
        lambda: AclProbeResult(
            status="PASS",
            stages=(),
            directory_removed=True,
            rights_evaluated=True,
            current_user_rights=True,
            system_rights=True,
            administrators_rights=True,
            broad_write_blocked=True,
        ),
    )
    monkeypatch.setattr(
        run,
        "_envelope_check",
        lambda: ReportCheck("envelope-and-rollback", ResultStatus.PASS, "PASS"),
    )
    monkeypatch.setattr(
        run,
        "_crash_check",
        lambda temp_dir: ReportCheck("crash-consistency-model", ResultStatus.PASS, "PASS"),
    )

    class Offline:
        status = "PASS"

    monkeypatch.setattr(run, "run_offline_smoke", lambda: Offline())


def _target_result(status: ResultStatus) -> object:
    from spikes.windows_encryption.windows_target_probe import (
        WindowsArchitectureEvidence,
        WindowsMachine,
        WindowsProductType,
        WindowsVersionEvidence,
        run_windows_target_probe,
    )

    def target_version(product: WindowsProductType) -> WindowsVersionEvidence:
        return WindowsVersionEvidence(10, 0, 22631, product, ResultStatus.PASS, "PASS")

    target_architecture = WindowsArchitectureEvidence(
        WindowsMachine.AMD64,
        WindowsMachine.UNKNOWN,
        8,
        ResultStatus.PASS,
        "PASS",
    )
    if status == ResultStatus.PASS:
        return run_windows_target_probe(
            lambda: target_version(WindowsProductType.WORKSTATION), lambda: target_architecture
        )
    return run_windows_target_probe(
        lambda: target_version(WindowsProductType.SERVER), lambda: target_architecture
    )


def test_build_report_uses_passing_windows_target_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spikes.windows_encryption import run

    _passing_report_dependencies(monkeypatch)
    monkeypatch.setattr(run, "run_windows_target_probe", lambda: _target_result(ResultStatus.PASS))
    report = build_report(tmp_path)
    assert report.windows_11_x64_result == ResultStatus.PASS
    assert "windows11-not-demonstrated" not in report.documented_limitations
    assert report.recommendation == "CONDITIONALLY_FEASIBLE"


def test_build_report_keeps_server_non_target_conditional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spikes.windows_encryption import run

    _passing_report_dependencies(monkeypatch)
    monkeypatch.setattr(
        run, "run_windows_target_probe", lambda: _target_result(ResultStatus.NOT_DEMONSTRATED)
    )
    report = build_report(tmp_path)
    checks = {check.identifier: check for check in report.checks}
    assert checks["windows-target-workstation"].status == ResultStatus.NOT_DEMONSTRATED
    assert checks["windows-11-x64"].status == ResultStatus.NOT_DEMONSTRATED
    assert report.windows_11_x64_result == ResultStatus.NOT_DEMONSTRATED
    assert "windows11-not-demonstrated" in report.documented_limitations
    assert report.recommendation == "CONDITIONALLY_FEASIBLE"


def test_windows_target_safe_report_contains_no_raw_private_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spikes.windows_encryption import run

    _passing_report_dependencies(monkeypatch)
    monkeypatch.setattr(
        run, "run_windows_target_probe", lambda: _target_result(ResultStatus.NOT_DEMONSTRATED)
    )
    text = report_to_json(build_report(tmp_path))
    for forbidden in (
        "hostname",
        "username",
        "domain",
        "SID",
        "registry",
        "GetLastError",
        "Traceback",
        str(tmp_path),
    ):
        assert forbidden not in text
