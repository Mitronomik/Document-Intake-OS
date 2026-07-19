from __future__ import annotations

from scripts import verify_pr006_storage


def test_manual_verification_format_does_not_turn_fail_into_pass() -> None:
    report = verify_pr006_storage.format_report({"publish": "FAIL"})
    assert "publish=FAIL" in report
    assert "publish=PASS" not in report


def test_manual_verification_main_returns_nonzero_on_failed_check(monkeypatch) -> None:
    monkeypatch.setattr(verify_pr006_storage, "run_checks", lambda: {"publish": "FAIL"})
    assert verify_pr006_storage.main() == 1


def test_sanitized_report_scanner_detects_contamination() -> None:
    assert verify_pr006_storage.report_is_sanitized("publish=PASS", ("secret",))
    assert not verify_pr006_storage.report_is_sanitized("publish=PASS secret", ("secret",))
