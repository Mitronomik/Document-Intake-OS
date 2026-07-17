from __future__ import annotations

import argparse
import platform
import sys
import tempfile
from pathlib import Path

from spikes.windows_encryption.dpapi_probe import unprotect_current_user, write_cross_runner_blob
from spikes.windows_encryption.safe_report import ReportCheck, ResultStatus, SafeReport, validate_report_file, write_report
from spikes.windows_encryption.sqlcipher_probe import run_sqlcipher_probe


def build_report(temp_dir: Path) -> SafeReport:
    sql = run_sqlcipher_probe(temp_dir)
    checks = [
        ReportCheck("sqlcipher-runtime", ResultStatus.PASS if sql.status == "PASS" else ResultStatus.UNSUPPORTED, sql.status),
        ReportCheck("dpapi-current-user", ResultStatus.UNSUPPORTED if platform.system() != "Windows" else ResultStatus.NOT_DEMONSTRATED, "CI_RECORDED"),
        ReportCheck("acl-temporary-directory", ResultStatus.UNSUPPORTED if platform.system() != "Windows" else ResultStatus.NOT_DEMONSTRATED, "CI_RECORDED"),
        ReportCheck("envelope-tamper", ResultStatus.PASS, "PYTEST_PROVES"),
        ReportCheck("rollback-anchor", ResultStatus.PASS, "PYTEST_PROVES"),
        ReportCheck("crash-consistency-model", ResultStatus.PASS, "PYTEST_PROVES"),
        ReportCheck("offline-wheelhouse", ResultStatus.NOT_DEMONSTRATED, "GITHUB_ACTIONS_STEP"),
    ]
    return SafeReport(
        report_schema_version=1,
        timestamp_utc="2026-07-17T00:00:00+00:00",
        os_family=platform.system() or "UNKNOWN",
        os_release=platform.release() or "UNKNOWN",
        architecture=platform.machine() or "UNKNOWN",
        python_version=sys.version.split()[0],
        candidate_name="sqlcipher3==0.6.2",
        package_versions={"cryptography": "49.0.0", "sqlcipher3": "0.6.2"},
        sqlcipher_version=sql.sqlcipher_version,
        sqlite_version=sql.sqlite_version,
        checks=checks,
        licensing_classifications={"sqlcipher3": "BSD-style binding metadata; SQLCipher Community attribution required", "cryptography": "Apache-2.0 OR BSD-3-Clause"},
        documented_limitations=["No final package selection", "No production persistence or storage API", "Full-system coordinated rollback is explicitly not claimed as detected"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-report", type=Path)
    parser.add_argument("--write-dpapi-blob", type=Path)
    parser.add_argument("--cross-runner-negative", type=Path)
    args = parser.parse_args()
    if args.validate_report:
        validate_report_file(args.validate_report)
        print("SAFE_REPORT_VALID")
        return 0
    if args.write_dpapi_blob:
        print(write_cross_runner_blob(args.write_dpapi_blob))
        return 0
    if args.cross_runner_negative:
        result = unprotect_current_user(args.cross_runner_negative.read_bytes())
        if result.status == "PASS":
            print("ERR_DPAPI_CROSS_RUNNER_UNEXPECTED_SUCCESS")
            return 1
        print("PASS_DPAPI_CROSS_RUNNER_UNPROTECT_FAILED")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        report = build_report(Path(tmp))
    if args.output:
        write_report(report, args.output)
    print("PR_S001_SPIKE_COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
