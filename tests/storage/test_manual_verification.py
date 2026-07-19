from __future__ import annotations

from scripts.verify_pr006_storage import format_report


def test_manual_verification_format_does_not_turn_fail_into_pass() -> None:
    report = format_report({"publish": "FAIL"})
    assert "publish=FAIL" in report
    assert "publish=PASS" not in report
