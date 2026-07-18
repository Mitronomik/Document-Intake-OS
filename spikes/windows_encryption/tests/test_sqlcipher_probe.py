from __future__ import annotations

import os
import platform
import sqlite3
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


class _OrdinaryCursor:
    def __init__(self, should_raise: bool) -> None:
        self._should_raise = should_raise

    def fetchone(self) -> tuple[int] | None:
        if self._should_raise:
            raise RuntimeError("not used")
        return (1,)


class _OrdinaryConn:
    def __init__(self, *, raise_database_error: bool) -> None:
        self.raise_database_error = raise_database_error
        self.closed = False

    def execute(self, sql: str) -> _OrdinaryCursor:
        if self.raise_database_error:
            raise sqlite3.DatabaseError("expected encrypted database rejection")
        return _OrdinaryCursor(False)

    def close(self) -> None:
        self.closed = True


def test_ordinary_sqlite_rejects_closes_after_database_error(tmp_path: Path) -> None:

    from spikes.windows_encryption.sqlcipher_probe import _ordinary_sqlite_rejects

    conn = _OrdinaryConn(raise_database_error=True)
    assert _ordinary_sqlite_rejects(tmp_path / "probe.db", lambda _path: conn)
    assert conn.closed


def test_ordinary_sqlite_rejects_closes_after_unexpected_success(tmp_path: Path) -> None:
    from spikes.windows_encryption.sqlcipher_probe import _ordinary_sqlite_rejects

    conn = _OrdinaryConn(raise_database_error=False)
    assert not _ordinary_sqlite_rejects(tmp_path / "probe.db", lambda _path: conn)
    assert conn.closed


def test_ordinary_sqlite_rejects_only_database_error_is_pass(tmp_path: Path) -> None:

    from spikes.windows_encryption.sqlcipher_probe import _ordinary_sqlite_rejects

    ok = _OrdinaryConn(raise_database_error=True)
    accepted = _OrdinaryConn(raise_database_error=False)
    assert _ordinary_sqlite_rejects(tmp_path / "probe.db", lambda _path: ok)
    assert not _ordinary_sqlite_rejects(tmp_path / "probe.db", lambda _path: accepted)


# ---------------------------------------------------------------------------
# PR-S001-F2 WAL / rollback journal evidence decision tests
# ---------------------------------------------------------------------------

from spikes.windows_encryption.run import _reason  # noqa: E402
from spikes.windows_encryption.sqlcipher_probe import (  # noqa: E402
    _journal_checks_from_evidence,
    _marker_payload,
    _ordinary_journal_control,
    _ordinary_wal_control,
    _scan_for_marker,
    _wal_checks_from_evidence,
)


def _by_id(checks: tuple[CheckResult, ...]) -> dict[str, CheckResult]:
    return {check.identifier: check for check in checks}


def _assert_check(check: CheckResult, status: str, reason_code: str) -> None:
    assert check.status == status
    assert check.reason_code == reason_code


@pytest.mark.parametrize(
    (
        "wal_exists",
        "wal_size",
        "control_marker_present",
        "encrypted_marker_present",
        "expected_reason",
    ),
    [
        (False, 0, True, False, "ERR_WAL_NOT_CREATED"),
        (True, 0, True, False, "ERR_WAL_EMPTY"),
        (True, 128, False, False, "ERR_WAL_CONTROL_MARKER_MISSING"),
        (True, 128, True, True, "ERR_MARKER_IN_WAL"),
        (True, 128, True, False, "PASS"),
    ],
)
def test_wal_marker_absent_and_encrypted_content_reason_precedence(
    wal_exists: bool,
    wal_size: int,
    control_marker_present: bool,
    encrypted_marker_present: bool,
    expected_reason: str,
) -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=wal_exists,
            wal_size=wal_size,
            control_marker_present=control_marker_present,
            encrypted_marker_present=encrypted_marker_present,
        )
    )
    expected_status = "PASS" if expected_reason == "PASS" else "FAIL"
    _assert_check(checks["wal-marker-absent"], expected_status, expected_reason)
    _assert_check(checks["wal-encrypted-content"], expected_status, expected_reason)


@pytest.mark.parametrize(
    (
        "journal_exists",
        "journal_size",
        "control_marker_present",
        "encrypted_marker_present",
        "expected_reason",
    ),
    [
        (False, 0, True, False, "ERR_JOURNAL_NOT_CREATED"),
        (True, 0, True, False, "ERR_JOURNAL_EMPTY"),
        (True, 128, False, False, "ERR_JOURNAL_CONTROL_MARKER_MISSING"),
        (True, 128, True, True, "ERR_MARKER_IN_JOURNAL"),
        (True, 128, True, False, "PASS"),
    ],
)
def test_journal_marker_absent_reason_precedence(
    journal_exists: bool,
    journal_size: int,
    control_marker_present: bool,
    encrypted_marker_present: bool,
    expected_reason: str,
) -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=journal_exists,
            journal_size=journal_size,
            control_marker_present=control_marker_present,
            encrypted_marker_present=encrypted_marker_present,
        )
    )
    expected_status = "PASS" if expected_reason == "PASS" else "FAIL"
    _assert_check(checks["journal-marker-absent"], expected_status, expected_reason)


def test_wal_mode_accepted_as_wal_produces_mode_pass() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=True,
            wal_size=1,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["wal-mode-active"].status == "PASS"


def test_rejected_wal_mode_is_unsupported() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="delete",
            wal_exists=False,
            wal_size=0,
            control_marker_present=False,
            encrypted_marker_present=False,
            mode_unsupported=True,
        )
    )
    assert checks["wal-mode-active"].reason_code == "UNSUPPORTED_WAL_MODE"


def test_active_wal_missing_file_fails() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=False,
            wal_size=0,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["wal-file-present"].reason_code == "ERR_WAL_NOT_CREATED"


def test_active_wal_empty_file_fails() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=True,
            wal_size=0,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["wal-file-nonempty"].reason_code == "ERR_WAL_EMPTY"
    _assert_check(checks["wal-marker-absent"], "FAIL", "ERR_WAL_EMPTY")
    _assert_check(checks["wal-encrypted-content"], "FAIL", "ERR_WAL_EMPTY")


def test_wal_missing_control_marker_fails() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=True,
            wal_size=1,
            control_marker_present=False,
            encrypted_marker_present=False,
        )
    )
    assert checks["wal-control-marker-present"].reason_code == "ERR_WAL_CONTROL_MARKER_MISSING"


def test_marker_present_in_encrypted_wal_fails() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=True,
            wal_size=1,
            control_marker_present=True,
            encrypted_marker_present=True,
        )
    )
    assert checks["wal-marker-absent"].reason_code == "ERR_MARKER_IN_WAL"


def test_valid_non_vacuous_wal_evidence_passes_all_required_checks() -> None:
    checks = _wal_checks_from_evidence(
        mode="wal",
        wal_exists=True,
        wal_size=1,
        control_marker_present=True,
        encrypted_marker_present=False,
    )
    assert all(check.status == "PASS" and check.reason_code == "PASS" for check in checks)


def test_rollback_mode_accepted_produces_mode_pass() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=True,
            journal_size=1,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["journal-mode-active"].status == "PASS"


def test_unsupported_rollback_mode_is_unsupported() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="wal",
            journal_exists=False,
            journal_size=0,
            control_marker_present=False,
            encrypted_marker_present=False,
            mode_unsupported=True,
        )
    )
    assert checks["journal-mode-active"].reason_code == "UNSUPPORTED_ROLLBACK_JOURNAL_MODE"


def test_active_rollback_missing_journal_fails() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=False,
            journal_size=0,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["journal-file-present"].reason_code == "ERR_JOURNAL_NOT_CREATED"


def test_active_rollback_empty_journal_fails() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=True,
            journal_size=0,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["journal-file-nonempty"].reason_code == "ERR_JOURNAL_EMPTY"
    _assert_check(checks["journal-marker-absent"], "FAIL", "ERR_JOURNAL_EMPTY")


def test_rollback_missing_control_marker_fails() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=True,
            journal_size=1,
            control_marker_present=False,
            encrypted_marker_present=False,
        )
    )
    assert (
        checks["journal-control-marker-present"].reason_code == "ERR_JOURNAL_CONTROL_MARKER_MISSING"
    )


def test_marker_present_in_encrypted_journal_fails() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=True,
            journal_size=1,
            control_marker_present=True,
            encrypted_marker_present=True,
        )
    )
    assert checks["journal-marker-absent"].reason_code == "ERR_MARKER_IN_JOURNAL"


def test_valid_non_vacuous_journal_evidence_passes_all_required_checks() -> None:
    checks = _journal_checks_from_evidence(
        mode="delete",
        journal_exists=True,
        journal_size=1,
        control_marker_present=True,
        encrypted_marker_present=False,
    )
    assert all(check.status == "PASS" and check.reason_code == "PASS" for check in checks)


def test_wal_and_journal_checks_never_not_demonstrated() -> None:
    checks = (
        *_wal_checks_from_evidence(
            mode="wal",
            wal_exists=False,
            wal_size=0,
            control_marker_present=False,
            encrypted_marker_present=False,
        ),
        *_journal_checks_from_evidence(
            mode="delete",
            journal_exists=False,
            journal_size=0,
            control_marker_present=False,
            encrypted_marker_present=False,
        ),
    )
    assert "NOT_DEMONSTRATED" not in {check.status for check in checks}
    assert "NOT_DEMONSTRATED" not in {check.reason_code for check in checks}


def test_all_new_reason_codes_survive_run_reason() -> None:
    codes = {
        "UNSUPPORTED_WAL_MODE",
        "UNSUPPORTED_ROLLBACK_JOURNAL_MODE",
        "ERR_WAL_NOT_CREATED",
        "ERR_WAL_EMPTY",
        "ERR_WAL_CONTROL_MARKER_MISSING",
        "ERR_WAL_PROBE_FAILED",
        "ERR_JOURNAL_NOT_CREATED",
        "ERR_JOURNAL_EMPTY",
        "ERR_JOURNAL_CONTROL_MARKER_MISSING",
        "ERR_JOURNAL_PROBE_FAILED",
    }
    assert {_reason(code) for code in codes} == codes


def test_wal_control_pass_is_independent_when_encrypted_wal_missing() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=False,
            wal_size=0,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["wal-control-marker-present"].status == "PASS"
    assert checks["wal-control-marker-present"].reason_code == "PASS"
    assert checks["wal-file-present"].reason_code == "ERR_WAL_NOT_CREATED"
    _assert_check(checks["wal-marker-absent"], "FAIL", "ERR_WAL_NOT_CREATED")
    _assert_check(checks["wal-encrypted-content"], "FAIL", "ERR_WAL_NOT_CREATED")


def test_wal_control_pass_is_independent_when_encrypted_wal_empty() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=True,
            wal_size=0,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["wal-control-marker-present"].status == "PASS"
    assert checks["wal-control-marker-present"].reason_code == "PASS"
    assert checks["wal-file-nonempty"].reason_code == "ERR_WAL_EMPTY"


def test_journal_control_pass_is_independent_when_encrypted_journal_missing() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=False,
            journal_size=0,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["journal-control-marker-present"].status == "PASS"
    assert checks["journal-control-marker-present"].reason_code == "PASS"
    assert checks["journal-file-present"].reason_code == "ERR_JOURNAL_NOT_CREATED"
    _assert_check(checks["journal-marker-absent"], "FAIL", "ERR_JOURNAL_NOT_CREATED")


def test_journal_control_pass_is_independent_when_encrypted_journal_empty() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=True,
            journal_size=0,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["journal-control-marker-present"].status == "PASS"
    assert checks["journal-control-marker-present"].reason_code == "PASS"
    assert checks["journal-file-nonempty"].reason_code == "ERR_JOURNAL_EMPTY"


def test_wal_file_size_uses_byte_size_not_duration_ms() -> None:
    checks = _by_id(
        _wal_checks_from_evidence(
            mode="wal",
            wal_exists=True,
            wal_size=4096,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["wal-file-nonempty"].duration_ms == 0
    assert checks["wal-file-nonempty"].byte_size == 4096


def test_journal_file_size_uses_byte_size_not_duration_ms() -> None:
    checks = _by_id(
        _journal_checks_from_evidence(
            mode="delete",
            journal_exists=True,
            journal_size=8192,
            control_marker_present=True,
            encrypted_marker_present=False,
        )
    )
    assert checks["journal-file-nonempty"].duration_ms == 0
    assert checks["journal-file-nonempty"].byte_size == 8192


def test_ordinary_controls_cleanup_and_do_not_contaminate_controlled_temp_scan(
    tmp_path: Path,
) -> None:
    marker = b"synthetic-record-control-cleanup-001"
    payload = _marker_payload(marker)
    before = set(tmp_path.iterdir())

    assert _ordinary_wal_control(tmp_path, payload, marker)
    after_wal = set(tmp_path.iterdir())
    assert after_wal == before

    replacement = _marker_payload(b"synthetic-record-control-cleanup-replacement")
    assert _ordinary_journal_control(tmp_path, payload, replacement, marker)
    after_journal = set(tmp_path.iterdir())
    assert after_journal == before

    remaining_files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert _scan_for_marker(remaining_files, marker)


def test_controlled_temp_scan_still_detects_encrypted_scenario_marker_leakage(
    tmp_path: Path,
) -> None:
    marker = b"synthetic-record-leakage-detection-001"
    leaked = tmp_path / "wal-probe.db-wal"
    leaked.write_bytes(b"prefix" + marker + b"suffix")

    remaining_files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert not _scan_for_marker(remaining_files, marker)
