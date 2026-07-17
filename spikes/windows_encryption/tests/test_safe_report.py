from __future__ import annotations

import json

import pytest

from spikes.windows_encryption.safe_report import ReportCheck, ResultStatus, SafeReport, report_to_json, validate_report_file


def test_safe_report_blocks_forbidden_fields_and_paths(tmp_path) -> None:
    report = SafeReport(1, "2026-07-17T00:00:00+00:00", "Windows", "11", "AMD64", "3.12", "sqlcipher3==0.6.2", checks=[ReportCheck("dpapi", ResultStatus.PASS, "PASS")])
    text = report_to_json(report)
    assert "plaintext" not in text.lower()
    path = tmp_path / "safe.json"
    path.write_text(text, encoding="utf-8")
    validate_report_file(path)
    data = json.loads(text)
    data["absolute_path"] = str(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="ERR_REPORT_FIELD_NOT_ALLOWLISTED"):
        validate_report_file(bad)
