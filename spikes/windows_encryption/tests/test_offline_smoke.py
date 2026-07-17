from __future__ import annotations

from spikes.windows_encryption.offline_smoke import offline_environment_note, run_offline_smoke


def test_offline_smoke_executes_or_reports_missing_dependency() -> None:
    result = run_offline_smoke()
    assert result.status in {
        "PASS",
        "UNSUPPORTED_DEPENDENCY_MISSING",
        "FAIL_WRONG_KEY_ACCEPTED",
        "FAIL_ORDINARY_SQLITE_ACCEPTED",
        "FAIL_AES_GCM",
    }
    assert offline_environment_note() in {
        "WHEELHOUSE_NO_INDEX_FIND_LINKS_SMOKE_ONLY",
        "UNSUPPORTED_NON_WINDOWS",
    }
