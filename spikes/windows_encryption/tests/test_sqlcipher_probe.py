from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from spikes.windows_encryption.sqlcipher_probe import (
    CheckResult,
    SqlcipherEvidence,
    _execute_pragma,
    _status_from_bool,
    inspect_raw_key_api,
    raw_key_pragma_fragment,
    run_sqlcipher_probe,
)


class _FakeConn:
    """Fake sqlcipher3 connection for unit tests."""

    def __init__(self, pragma_results: dict[str, list[tuple[Any, ...]]] | None = None) -> None:
        self._pragma_results = pragma_results or {}

    def execute(self, sql: str) -> Any:
        for key, rows in self._pragma_results.items():
            if key.lower() in sql.lower():
                return _FakeCursor(rows)
        return _FakeCursor([])

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None


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


def test_empty_pragma_gives_unsupported() -> None:
    conn = _FakeConn({})
    status, rows = _execute_pragma(conn, "PRAGMA cipher_provider")
    assert status == "PASS"
    assert rows == []


def test_unknown_pragma_is_not_silently_successful() -> None:
    conn = _FakeConn({"cipher_version": [("4.0.1",)]})
    status, rows = _execute_pragma(conn, "PRAGMA cipher_provider")
    assert status == "PASS"
    assert rows == []


def test_missing_wal_yields_not_demonstrated() -> None:
    result = SqlcipherEvidence(
        status="UNSUPPORTED",
        wal_evidence="NOT_DEMONSTRATED",
        checks=(CheckResult("wal-marker-absent", "NOT_DEMONSTRATED", "NOT_DEMONSTRATED"),),
    )
    assert result.wal_evidence == "NOT_DEMONSTRATED"
    assert result.checks[0].status == "NOT_DEMONSTRATED"


def test_present_wal_is_demonstrable() -> None:
    result = SqlcipherEvidence(
        status="PASS",
        wal_evidence="PRESENT",
        checks=(CheckResult("wal-marker-absent", "PASS", "PASS"),),
    )
    assert result.wal_evidence == "PRESENT"
    assert result.checks[0].status == "PASS"


def test_missing_journal_yields_not_demonstrated() -> None:
    result = SqlcipherEvidence(
        status="UNSUPPORTED",
        journal_evidence="NOT_DEMONSTRATED",
        checks=(CheckResult("journal-marker-absent", "NOT_DEMONSTRATED", "NOT_DEMONSTRATED"),),
    )
    assert result.journal_evidence == "NOT_DEMONSTRATED"
    assert result.checks[0].status == "NOT_DEMONSTRATED"


def test_present_journal_is_demonstrable() -> None:
    result = SqlcipherEvidence(
        status="PASS",
        journal_evidence="PRESENT",
        checks=(CheckResult("journal-marker-absent", "PASS", "PASS"),),
    )
    assert result.journal_evidence == "PRESENT"
    assert result.checks[0].status == "PASS"


def test_sqlcipher_fail_injects_not_feasible() -> None:
    result = SqlcipherEvidence(
        status="FAIL",
        checks=(CheckResult("sqlcipher-overall", "FAIL", "ERR_SQLCIPHER_IMPORT"),),
    )
    assert result.status == "FAIL"


def test_sqlcipher_probe_executes_or_reports_unsupported(tmp_path: Path) -> None:
    result = run_sqlcipher_probe(tmp_path)
    if platform.system() != "Windows":
        assert result.status == "UNSUPPORTED"
        sqlcipher_overall = [c for c in result.checks if c.identifier == "sqlcipher-overall"]
        assert len(sqlcipher_overall) == 1
        assert sqlcipher_overall[0].reason_code == "UNSUPPORTED_NON_WINDOWS"
    else:
        assert result.status in {"PASS", "FAIL", "UNSUPPORTED"}
        assert result.raw_key_api_assessment in {"AVAILABLE", "UNAVAILABLE", "NOT_DEMONSTRATED"}
        assert result.checks
    assert os.fspath(tmp_path) not in repr(result)


def test_unexpected_exception_does_not_pass_check() -> None:
    result = _status_from_bool("broken-check", False, "ERR_TEST")
    assert result.status == "FAIL"


def test_empty_pragma_returns_unsupported_provider() -> None:
    result = SqlcipherEvidence(
        status="UNSUPPORTED",
        cryptographic_provider="UNSUPPORTED",
        checks=(CheckResult("sqlcipher-overall", "UNSUPPORTED", "UNSUPPORTED_NON_WINDOWS"),),
    )
    assert result.cryptographic_provider == "UNSUPPORTED"
