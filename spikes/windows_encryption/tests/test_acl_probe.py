from __future__ import annotations

import platform

from spikes.windows_encryption.acl_probe import probe_directory_is_removed, run_acl_probe


def test_acl_probe_returns_stable_status_and_no_raw_output() -> None:
    result = run_acl_probe()
    if platform.system() != "Windows":
        assert result.status == "UNSUPPORTED_NON_WINDOWS"
    else:
        assert result.status in {"PASS", "FAIL_BROAD_WRITE", "ERR_ACL_PROBE_FAILED"}
    assert "S-" not in repr(result)
    assert "icacls" not in repr(result).lower()


def test_acl_probe_cleans_up_directory() -> None:
    assert probe_directory_is_removed()
