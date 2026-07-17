from __future__ import annotations

import json
import os

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


def test_safe_report_allowlist_blocks_unknown_fields_and_paths(tmp_path) -> None:
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


def test_generated_report_omits_runtime_secret_values(tmp_path, capsys) -> None:
    key = os.urandom(32)
    marker = b"synthetic-record-test-marker"
    report = build_report(tmp_path)
    text = report_to_json(report)
    captured = capsys.readouterr()
    combined = text + captured.out + captured.err
    assert key.hex() not in combined
    assert marker.decode() not in combined
    assert str(tmp_path) not in combined
    assert "Traceback" not in combined
