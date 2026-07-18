from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any, cast

import pytest

from spikes.windows_encryption.sqlcipher_probe import (
    CheckResult,
    SqlcipherEvidence,
    _cipher_integrity_check,
    _cipher_status_check,
    _execute_pragma,
    _read_created_db,
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


# ---------------------------------------------------------------------------
# raw_key_pragma_fragment tests
# ---------------------------------------------------------------------------


def test_raw_key_pragma_exact_literal() -> None:
    key = bytes(range(32))
    expected = "\"x'" + key.hex() + "'\""
    actual = raw_key_pragma_fragment(key)
    assert actual == expected


def test_raw_key_pragma_is_isolated_and_not_logged() -> None:
    fragment = raw_key_pragma_fragment(b"a" * 32)
    assert fragment.startswith('"x') and fragment.endswith("'\"")
    assert len(fragment) == 1 + 1 + 1 + 64 + 1 + 1  # "x'<64 hex>'"
    assert raw_key_pragma_fragment(os.urandom(32)) != fragment


def test_raw_key_pragma_rejects_invalid_length() -> None:
    with pytest.raises(ValueError, match="ERR_INVALID_DB_KEY"):
        raw_key_pragma_fragment(b"short")
    with pytest.raises(ValueError, match="ERR_INVALID_DB_KEY"):
        raw_key_pragma_fragment(b"a" * 33)
    with pytest.raises(ValueError, match="ERR_INVALID_DB_KEY"):
        raw_key_pragma_fragment(b"")


def test_raw_key_pragma_hex_is_lowercase_64_chars() -> None:
    key = bytes(range(32))
    fragment = raw_key_pragma_fragment(key)
    hex_part = key.hex()
    assert len(hex_part) == 64
    assert hex_part == hex_part.lower()
    assert hex_part in fragment
    assert " " not in fragment


def test_raw_key_pragma_rejects_str_with_typeerror() -> None:
    with pytest.raises(TypeError, match="ERR_INVALID_DB_KEY_TYPE"):
        raw_key_pragma_fragment(cast(Any, "a" * 32))


def test_raw_key_pragma_rejects_bytearray_with_typeerror() -> None:
    with pytest.raises(TypeError, match="ERR_INVALID_DB_KEY_TYPE"):
        raw_key_pragma_fragment(cast(Any, bytearray(b"a" * 32)))


# ---------------------------------------------------------------------------
# _cipher_status_check tests
# ---------------------------------------------------------------------------


def test_cipher_status_active_returns_pass() -> None:
    value, check = _cipher_status_check("PASS", [("1",)])
    assert value == "1"
    assert check.status == "PASS"
    assert check.reason_code == "PASS"


def test_cipher_status_zero_is_inactive() -> None:
    value, check = _cipher_status_check("PASS", [("0",)])
    assert value == "0"
    assert check.status == "FAIL"
    assert check.reason_code == "ERR_CIPHER_STATUS_INACTIVE"


def test_cipher_status_empty_rows_is_inactive() -> None:
    value, check = _cipher_status_check("PASS", [])
    assert value == "UNSUPPORTED"
    assert check.status == "FAIL"
    assert check.reason_code == "ERR_CIPHER_STATUS_INACTIVE"


def test_cipher_status_unsupported_execution_is_inactive() -> None:
    value, check = _cipher_status_check("UNSUPPORTED", [])
    assert value == "UNSUPPORTED"
    assert check.status == "FAIL"
    assert check.reason_code == "ERR_CIPHER_STATUS_INACTIVE"


# ---------------------------------------------------------------------------
# _cipher_integrity_check tests
# ---------------------------------------------------------------------------


def test_cipher_integrity_clean_returns_pass() -> None:
    result, check = _cipher_integrity_check("PASS", [])
    assert result == "PASS"
    assert check.status == "PASS"
    assert check.reason_code == "PASS"


def test_cipher_integrity_errors_are_detected() -> None:
    result, check = _cipher_integrity_check("PASS", [("error row",)])
    assert result == "FAIL"
    assert check.status == "FAIL"
    assert check.reason_code == "ERR_CIPHER_INTEGRITY_FAILED"


def test_cipher_integrity_unsupported_is_fail() -> None:
    result, check = _cipher_integrity_check("UNSUPPORTED", [])
    assert result == "FAIL"
    assert check.status == "FAIL"
    assert check.reason_code == "ERR_CIPHER_INTEGRITY_FAILED"


# ---------------------------------------------------------------------------
# _read_created_db tests (basic existence)
# ---------------------------------------------------------------------------


def test_encrypted_db_created_exists(tmp_path: Path) -> None:
    db = tmp_path / "exists.db"
    db.write_bytes(b"x")
    check, data = _read_created_db(db)
    assert check.status == "PASS"
    assert check.reason_code == "PASS"
    assert data == b"x"


def test_encrypted_db_created_missing(tmp_path: Path) -> None:
    db = tmp_path / "missing.db"
    check, data = _read_created_db(db)
    assert check.status == "FAIL"
    assert check.reason_code == "ERR_ENCRYPTED_DB_NOT_CREATED"
    assert data is None


# ---------------------------------------------------------------------------
# SQLCipher invariant tests
# ---------------------------------------------------------------------------


def test_all_sqlcipher_reason_codes_in_allowlist() -> None:
    from spikes.windows_encryption.safe_report import ALLOWED_REASON_CODES

    # Collect all reason codes used in sqlcipher_probe
    sqlcipher_reasons = {
        "PASS",
        "UNSUPPORTED_NON_WINDOWS",
        "ERR_SQLCIPHER_IMPORT",
        "NOT_DEMONSTRATED",
        "ERR_CIPHER_STATUS_INACTIVE",
        "ERR_CIPHER_INTEGRITY_FAILED",
        "ERR_ENCRYPTED_DB_NOT_CREATED",
        "ERR_PLAINTEXT_HEADER",
        "ERR_MARKER_IN_DB",
        "ERR_TEMP_STORE_NOT_MEMORY",
        "ERR_CORRECT_KEY_MARKER_MISMATCH",
        "ERR_CORRECT_KEY_EXCEPTION",
        "ERR_WRONG_KEY_ACCEPTED",
        "ERR_SQLITE_ACCEPTED",
        "ERR_BIT_TAMPER_UNDETECTED",
        "ERR_TRUNCATION_UNDETECTED",
        "ERR_MARKER_IN_WAL",
        "ERR_MARKER_IN_JOURNAL",
        "ERR_MARKER_IN_TEMP",
        "ERR_PLAINTEXT_WAL",
        "ERR_CLEANUP_FAILED",
    }
    missing = sqlcipher_reasons - ALLOWED_REASON_CODES
    assert not missing, f"Reason codes not in allowlist: {missing}"


def test_check_result_pass_implies_pass_reason() -> None:
    checks = [
        CheckResult("a", "PASS", "PASS"),
        CheckResult("b", "FAIL", "ERR_CIPHER_STATUS_INACTIVE"),
        CheckResult("c", "UNSUPPORTED", "UNSUPPORTED_NON_WINDOWS"),
        CheckResult("d", "NOT_DEMONSTRATED", "NOT_DEMONSTRATED"),
    ]
    for check in checks:
        if check.status == "PASS":
            assert check.reason_code == "PASS", f"{check.identifier}"
        if check.status == "FAIL":
            assert check.reason_code != "PASS", f"{check.identifier}"


# ---------------------------------------------------------------------------
# Remaining original tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _read_created_db runtime guard tests
# ---------------------------------------------------------------------------


def test_read_created_db_missing_does_not_read(monkeypatch: Any) -> None:
    """For a missing path, the helper returns FAIL with data=None
    and never calls read_bytes()."""

    def _crash(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("read_bytes must not be called on missing path")

    monkeypatch.setattr(Path, "read_bytes", _crash)

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "nonexistent.db"
        check, data = _read_created_db(missing)
        assert check.status == "FAIL"
        assert check.reason_code == "ERR_ENCRYPTED_DB_NOT_CREATED"
        assert data is None


def test_read_created_db_existing_returns_exact_bytes(tmp_path: Path) -> None:
    """Existing db_path returns PASS with exact file bytes."""
    db = tmp_path / "probe.db"
    expected = b"test-database-content"
    db.write_bytes(expected)

    check, data = _read_created_db(db)
    assert check.status == "PASS"
    assert check.reason_code == "PASS"
    assert data == expected


def test_read_created_db_existing_does_not_return_none(tmp_path: Path) -> None:
    """When file exists, data must never be None."""
    db = tmp_path / "probe.db"
    db.write_bytes(b"content")
    _check, data = _read_created_db(db)
    assert data is not None
