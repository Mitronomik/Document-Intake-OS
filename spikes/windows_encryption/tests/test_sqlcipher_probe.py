from __future__ import annotations

import os
import platform

from spikes.windows_encryption.sqlcipher_probe import raw_key_pragma_fragment, run_sqlcipher_probe


def test_raw_key_pragma_is_isolated() -> None:
    fragment = raw_key_pragma_fragment(b"a" * 32)
    assert fragment.startswith("x'")
    assert fragment.endswith("'")


def test_sqlcipher_probe_reports_unsupported_on_non_windows(tmp_path) -> None:
    result = run_sqlcipher_probe(tmp_path)
    if platform.system() != "Windows":
        assert result.status == "UNSUPPORTED_NON_WINDOWS"
    else:
        assert result.status in {"PASS", "FAIL"}
    assert os.fspath(tmp_path) not in repr(result)
