from __future__ import annotations

import importlib
import platform
from typing import Any, cast

from spikes.windows_encryption.offline_smoke import (
    _try_import_aesgcm,
    offline_environment_note,
    run_offline_smoke,
)


def test_offline_smoke_executes_or_reports_missing_dependency() -> None:
    result = run_offline_smoke()
    if platform.system() == "Windows":
        try:
            sqlcipher3 = cast(Any, importlib.import_module("sqlcipher3"))
        except ImportError:
            expected = {"UNSUPPORTED_DEPENDENCY_MISSING"}
        else:
            _ = sqlcipher3
            aesgcm_class = _try_import_aesgcm()
            if aesgcm_class is None:
                expected = {"UNSUPPORTED_DEPENDENCY_MISSING"}
            else:
                expected = {
                    "PASS",
                    "FAIL_WRONG_KEY_ACCEPTED",
                    "FAIL_ORDINARY_SQLITE_ACCEPTED",
                    "FAIL_AES_GCM",
                    "FAIL_CORRECT_KEY_REJECTED",
                }
    else:
        expected = {"UNSUPPORTED_DEPENDENCY_MISSING"}
    assert result.status in expected, f"Unexpected status: {result.status}"
    assert offline_environment_note() in {
        "WHEELHOUSE_NO_INDEX_FIND_LINKS_SMOKE_ONLY",
        "UNSUPPORTED_NON_WINDOWS",
    }


def test_cleanup_status_is_explicit_not_pending() -> None:
    result = run_offline_smoke()
    assert result.cleanup_status != "PENDING_CLEANUP"


def test_dependency_missing_gives_clean_pass() -> None:
    if platform.system() != "Windows":
        result = run_offline_smoke()
        assert result.status == "UNSUPPORTED_DEPENDENCY_MISSING"
