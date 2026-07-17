from __future__ import annotations

import os
import platform

from spikes.windows_encryption.sqlcipher_probe import (
    inspect_raw_key_api,
    raw_key_pragma_fragment,
    run_sqlcipher_probe,
)


def test_raw_key_pragma_is_isolated_and_not_logged() -> None:
    fragment = raw_key_pragma_fragment(b"a" * 32)
    assert fragment.startswith("x'") and fragment.endswith("'")
    assert raw_key_pragma_fragment(os.urandom(32)) != fragment


def test_raw_key_api_inspection() -> None:
    class Binding:
        def setkey(self) -> None:  # pragma: no cover
            pass

    assert inspect_raw_key_api(Binding) == "AVAILABLE"
    assert inspect_raw_key_api(object()) == "UNAVAILABLE"


def test_sqlcipher_probe_executes_or_reports_unsupported(tmp_path) -> None:
    result = run_sqlcipher_probe(tmp_path)
    if platform.system() != "Windows":
        assert result.status == "UNSUPPORTED"
        assert result.checks[0].reason_code == "UNSUPPORTED_NON_WINDOWS"
    else:
        assert result.status in {"PASS", "FAIL", "UNSUPPORTED"}
        assert result.raw_key_api_assessment in {"AVAILABLE", "UNAVAILABLE", "NOT_DEMONSTRATED"}
        assert result.checks
    assert os.fspath(tmp_path) not in repr(result)
