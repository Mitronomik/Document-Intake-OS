from __future__ import annotations

import argparse
import importlib.metadata
import platform
import sys
import tempfile
from pathlib import Path

from spikes.windows_encryption.acl_probe import AclProbeResult, run_acl_probe
from spikes.windows_encryption.crash_consistency_probe import (
    FailurePoint,
    reconcile,
    run_staged_sequence,
)
from spikes.windows_encryption.dpapi_probe import (
    create_validated_cross_runner_blob,
    unprotect_current_user,
)
from spikes.windows_encryption.envelope_probe import (
    decrypt_envelope,
    encrypt_envelope,
    expected_state_for,
    verify_expected_state,
)
from spikes.windows_encryption.offline_smoke import run_offline_smoke
from spikes.windows_encryption.safe_report import (
    PackageEvidence,
    ReportCheck,
    ResultStatus,
    SafeReport,
    validate_report_file,
    write_report,
)
from spikes.windows_encryption.sqlcipher_probe import (
    CheckResult,
    run_sqlcipher_probe,
)


def _status(value: str) -> ResultStatus:
    if value == "PASS":
        return ResultStatus.PASS
    if value == "UNSUPPORTED" or value.startswith("UNSUPPORTED"):
        return ResultStatus.UNSUPPORTED
    if value == "NOT_DEMONSTRATED":
        return ResultStatus.NOT_DEMONSTRATED
    return ResultStatus.FAIL


def _reason(value: str) -> str:
    allowed = {
        "PASS",
        "UNSUPPORTED_NON_WINDOWS",
        "UNSUPPORTED_DEPENDENCY_MISSING",
        "NOT_DEMONSTRATED",
        "ERR_SQLCIPHER_IMPORT",
        "ERR_ACL_PROBE_FAILED",
        "ERR_ACL_CURRENT_USER_RIGHTS",
        "ERR_ACL_SYSTEM_RIGHTS",
        "ERR_ACL_ADMINISTRATORS_RIGHTS",
        "ERR_ACL_BROAD_WRITE",
        "ERR_ACL_CLEANUP_FAILED",
        "ERR_OFFLINE_SMOKE",
        "ERR_CRASH_MODEL",
        "ERR_ENVELOPE_AUTH_FAILED",
        "ERR_ROLLBACK_UNDETECTED",
        "ERR_DPAPI_SUBPROCESS_KEY_MISMATCH",
        "ERR_DPAPI_SUBPROCESS_VERIFY_FAILED",
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
        "ERR_MARKER_IN_TEMP",
        "ERR_PLAINTEXT_WAL",
        "ERR_CIPHER_STATUS_INACTIVE",
        "ERR_CIPHER_INTEGRITY_FAILED",
        "ERR_ENCRYPTED_DB_NOT_CREATED",
    }
    return value if value in allowed else "FAIL"


def _acl_cleanup_check(acl_result: AclProbeResult) -> ReportCheck:
    return ReportCheck(
        "acl-directory-cleanup",
        ResultStatus.PASS if acl_result.directory_removed else ResultStatus.FAIL,
        "PASS" if acl_result.directory_removed else "ERR_ACL_CLEANUP_FAILED",
    )


def _acl_checks(acl_result: AclProbeResult) -> list[ReportCheck]:
    if acl_result.status == "UNSUPPORTED_NON_WINDOWS":
        return [
            *(
                ReportCheck(identifier, ResultStatus.UNSUPPORTED, "UNSUPPORTED_NON_WINDOWS")
                for identifier in (
                    "acl-current-user-rights",
                    "acl-system-rights",
                    "acl-administrators-rights",
                    "acl-broad-write-blocked",
                )
            ),
            _acl_cleanup_check(acl_result),
        ]
    if acl_result.status == "ERR_ACL_PROBE_FAILED":
        return [
            *(
                ReportCheck(identifier, ResultStatus.FAIL, "ERR_ACL_PROBE_FAILED")
                for identifier in (
                    "acl-current-user-rights",
                    "acl-system-rights",
                    "acl-administrators-rights",
                    "acl-broad-write-blocked",
                )
            ),
            _acl_cleanup_check(acl_result),
        ]
    return [
        ReportCheck(
            "acl-current-user-rights",
            ResultStatus.PASS if acl_result.current_user_rights else ResultStatus.FAIL,
            "PASS" if acl_result.current_user_rights else "ERR_ACL_CURRENT_USER_RIGHTS",
        ),
        ReportCheck(
            "acl-system-rights",
            ResultStatus.PASS if acl_result.system_rights else ResultStatus.FAIL,
            "PASS" if acl_result.system_rights else "ERR_ACL_SYSTEM_RIGHTS",
        ),
        ReportCheck(
            "acl-administrators-rights",
            ResultStatus.PASS if acl_result.administrators_rights else ResultStatus.FAIL,
            "PASS" if acl_result.administrators_rights else "ERR_ACL_ADMINISTRATORS_RIGHTS",
        ),
        ReportCheck(
            "acl-broad-write-blocked",
            ResultStatus.PASS if acl_result.broad_write_blocked else ResultStatus.FAIL,
            "PASS" if acl_result.broad_write_blocked else "ERR_ACL_BROAD_WRITE",
        ),
        _acl_cleanup_check(acl_result),
    ]


def _check_from_sql(check: CheckResult) -> ReportCheck:
    return ReportCheck(
        check.identifier,
        _status(check.status),
        _reason(check.reason_code),
        check.duration_ms,
        check.byte_size,
    )


def _package(name: str) -> PackageEvidence:
    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        version = "UNSUPPORTED"
    return PackageEvidence(name, version)


def _envelope_check() -> ReportCheck:
    try:
        import os

        key = os.urandom(32)
        payload = os.urandom(32)
        envelope = encrypt_envelope(key, payload, "artifact-0001", "application-octet-stream", 1, 1)
        recovered = decrypt_envelope(key, envelope, "artifact-0001", "application-octet-stream", 1)
        record = expected_state_for(envelope)
        if recovered == payload and verify_expected_state(envelope, record).value == "PASS":
            return ReportCheck("envelope-and-rollback", ResultStatus.PASS, "PASS")
        return ReportCheck("envelope-and-rollback", ResultStatus.FAIL, "ERR_ROLLBACK_UNDETECTED")
    except RuntimeError:
        return ReportCheck(
            "envelope-and-rollback", ResultStatus.UNSUPPORTED, "UNSUPPORTED_DEPENDENCY_MISSING"
        )
    except ValueError:
        return ReportCheck("envelope-and-rollback", ResultStatus.FAIL, "ERR_ENVELOPE_AUTH_FAILED")


def _crash_check(temp_dir: Path) -> ReportCheck:
    record, temp_path, final_path = run_staged_sequence(
        temp_dir / "crash", FailurePoint.AFTER_ACTIVE_FINALIZATION
    )
    status = reconcile(record, final_path, temp_path)
    if status.value == "ACTIVE":
        return ReportCheck("crash-consistency-model", ResultStatus.PASS, "PASS")
    return ReportCheck("crash-consistency-model", ResultStatus.FAIL, "ERR_CRASH_MODEL")


def build_report(temp_dir: Path) -> SafeReport:
    sql = run_sqlcipher_probe(temp_dir / "sqlcipher")
    checks = [_check_from_sql(check) for check in sql.checks]
    sqlcipher_overall_status = _status(sql.status)
    sqlcipher_overall_reason = "PASS" if sql.status == "PASS" else _reason(sql.status)
    checks.append(
        ReportCheck("sqlcipher-overall", sqlcipher_overall_status, sqlcipher_overall_reason)
    )
    acl_result = run_acl_probe()
    checks.extend(_acl_checks(acl_result))
    checks.append(_envelope_check())
    checks.append(_crash_check(temp_dir))
    offline = run_offline_smoke()
    checks.append(
        ReportCheck(
            "offline-smoke",
            _status(offline.status),
            "PASS" if offline.status == "PASS" else "ERR_OFFLINE_SMOKE",
        )
    )
    recommendation = "CONDITIONALLY_FEASIBLE"
    if sql.status == "FAIL" or any(check.status == ResultStatus.FAIL for check in checks):
        recommendation = "NOT_FEASIBLE"
    safe_report_mod = __import__(
        "spikes.windows_encryption.safe_report", fromlist=["utc_timestamp"]
    )
    return SafeReport(
        report_schema_version=1,
        timestamp_utc=safe_report_mod.utc_timestamp(),
        os_family=platform.system() or "UNKNOWN",
        os_release=platform.release() or "UNKNOWN",
        architecture=platform.machine() or "UNKNOWN",
        python_version=sys.version.split()[0],
        candidate_name="sqlcipher3-0.6.2",
        packages=[_package("cryptography"), _package("sqlcipher3")],
        sqlcipher_version=sql.sqlcipher_version,
        sqlite_version=sql.sqlite_version,
        checks=checks,
        licensing_classifications=[
            "binding-metadata",
            "sqlcipher-community-attribution",
            "legal-approval-required",
        ],
        documented_limitations=[
            "no-final-package-selection",
            "no-production-api",
            "windows11-not-demonstrated",
        ],
        recommendation=recommendation,
        windows_11_x64_result=ResultStatus.NOT_DEMONSTRATED,
    )


def _write_dpapi_blob(path: Path) -> int:
    status = create_validated_cross_runner_blob(path)
    print(status)
    return 0 if status == "PASS" else 1


def _cross_runner_negative(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        print("ERR_DPAPI_ARTIFACT_INVALID")
        return 1
    result = unprotect_current_user(path.read_bytes())
    print(result.status)
    return 0 if result.status == "ERR_DPAPI_UNPROTECT_FAILED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-report", type=Path)
    parser.add_argument("--write-dpapi-blob", type=Path)
    parser.add_argument("--cross-runner-negative", type=Path)
    args = parser.parse_args()
    if args.validate_report is not None:
        validate_report_file(args.validate_report)
        print("SAFE_REPORT_VALID")
        return 0
    if args.write_dpapi_blob is not None:
        return _write_dpapi_blob(args.write_dpapi_blob)
    if args.cross_runner_negative is not None:
        return _cross_runner_negative(args.cross_runner_negative)
    with tempfile.TemporaryDirectory() as tmp:
        report = build_report(Path(tmp))
    if args.output is not None:
        write_report(report, args.output)
    print("PR_S001_SPIKE_COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
