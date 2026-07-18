from __future__ import annotations

import importlib
import importlib.metadata
import os
import platform
import shutil
import sqlite3
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

SYNTHETIC_MARKER_PREFIX = b"synthetic-record-"


class ConnectionLike(Protocol):
    def execute(self, sql: str) -> Any: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class CheckResult:
    identifier: str
    status: str
    reason_code: str
    duration_ms: int = 0
    byte_size: int = 0


@dataclass(frozen=True)
class SqlcipherEvidence:
    status: str
    binding_version: str = "UNSUPPORTED"
    sqlcipher_version: str = "UNSUPPORTED"
    sqlite_version: str = "UNSUPPORTED"
    cipher_status: str = "UNSUPPORTED"
    integrity_result: str = "UNSUPPORTED"
    compile_options: tuple[str, ...] = ()
    cryptographic_provider: str = "UNSUPPORTED"
    journal_mode: str = "UNSUPPORTED"
    temp_store: str = "UNSUPPORTED"
    raw_key_api_assessment: str = "NOT_DEMONSTRATED"
    logging_status: str = "UNSUPPORTED"
    hmac_evidence: str = "NOT_DEMONSTRATED"
    wal_evidence: str = "NOT_DEMONSTRATED"
    journal_evidence: str = "NOT_DEMONSTRATED"
    checks: tuple[CheckResult, ...] = ()


def raw_key_pragma_fragment(key: bytes) -> str:
    if not isinstance(key, bytes):
        raise TypeError("ERR_INVALID_DB_KEY_TYPE")
    if len(key) != 32:
        raise ValueError("ERR_INVALID_DB_KEY")
    return "\"x'" + key.hex() + "'\""


def inspect_raw_key_api(binding: Any) -> str:
    names = {name.lower() for name in dir(binding)}
    if {"key", "setkey", "rekey", "bind_key"} & names:
        return "AVAILABLE"
    return "UNAVAILABLE"


def _execute_pragma(conn: Any, statement: str) -> tuple[str, list[tuple[Any, ...]]]:
    try:
        rows = list(conn.execute(statement).fetchall())
    except Exception:
        return "UNSUPPORTED", []
    return "PASS", rows


def _key_connection(conn: Any, key: bytes) -> None:
    conn.execute("PRAGMA key = " + raw_key_pragma_fragment(key))
    conn.execute("PRAGMA temp_store=MEMORY")


def _status_from_bool(identifier: str, value: bool, fail_reason: str) -> CheckResult:
    return CheckResult(identifier, "PASS" if value else "FAIL", "PASS" if value else fail_reason)


def _cipher_status_check(status: str, rows: list[tuple[Any, ...]]) -> tuple[str, CheckResult]:
    """Return (cipher_status_value, CheckResult).

    cipher_status_value is the raw PRAGMA value (for SqlcipherEvidence.cipher_status).
    CheckResult has semantic status/reason_code.
    """
    if status == "PASS" and rows and str(rows[0][0]) == "1":
        return "1", CheckResult("cipher-status", "PASS", "PASS")
    raw_value = str(rows[0][0]) if status == "PASS" and rows else "UNSUPPORTED"
    return raw_value, CheckResult("cipher-status", "FAIL", "ERR_CIPHER_STATUS_INACTIVE")


def _cipher_integrity_check(status: str, rows: list[tuple[Any, ...]]) -> tuple[str, CheckResult]:
    """Return (integrity_result, CheckResult).

    cipher_integrity_check returns one row per error; empty means clean.
    """
    if status == "PASS" and not rows:
        return "PASS", CheckResult("cipher-integrity", "PASS", "PASS")
    return "FAIL", CheckResult("cipher-integrity", "FAIL", "ERR_CIPHER_INTEGRITY_FAILED")


def _read_created_db(db_path: Path) -> tuple[CheckResult, bytes | None]:
    """Return (CheckResult, data_or_None).

    If db_path does not exist:
      - returns FAIL / ERR_ENCRYPTED_DB_NOT_CREATED with data=None
      - never calls read_bytes()
    If db_path exists:
      - returns PASS / PASS with exact file bytes.
    """
    if not db_path.exists():
        return (
            CheckResult("encrypted-db-created", "FAIL", "ERR_ENCRYPTED_DB_NOT_CREATED"),
            None,
        )
    return (
        CheckResult("encrypted-db-created", "PASS", "PASS"),
        db_path.read_bytes(),
    )


def _ordinary_sqlite_rejects(
    db_path: Path,
    connect: Callable[..., ConnectionLike] = sqlite3.connect,
) -> bool:
    ordinary_conn = connect(db_path)
    try:
        ordinary_conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return False
    except sqlite3.DatabaseError:
        return True
    finally:
        ordinary_conn.close()


def _scan_for_marker(paths: list[Path], marker: bytes) -> bool:
    return all(marker not in path.read_bytes() for path in paths if path.exists())


def _corruption_detected(sqlcipher3: Any, source: Path, key: bytes, mutate: str) -> bool:
    target = source.with_name(source.stem + f"-{mutate}.db")
    shutil.copy2(source, target)
    data = bytearray(target.read_bytes())
    if mutate == "bit" and len(data) > 128:
        data[128] ^= 0x01
    elif mutate == "truncate" and len(data) > 128:
        data = data[: len(data) // 2]
    target.write_bytes(data)
    conn = sqlcipher3.connect(str(target))
    try:
        _key_connection(conn, key)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        status, rows = _execute_pragma(conn, "PRAGMA cipher_integrity_check")
        return status == "PASS" and bool(rows)
    except Exception:
        return True
    finally:
        conn.close()


def _marker_payload(marker: bytes) -> bytes:
    return marker * 512


def _single_path_marker_absent(path: Path, marker: bytes) -> bool:
    return marker not in path.read_bytes()


def _mode_from_rows(rows: list[tuple[Any, ...]]) -> str:
    if not rows or rows[0][0] is None:
        return ""
    return str(rows[0][0]).strip().lower()


def _wal_checks_from_evidence(
    *,
    mode: str,
    wal_exists: bool,
    wal_size: int,
    control_marker_present: bool,
    encrypted_marker_present: bool,
    mode_unsupported: bool = False,
) -> tuple[CheckResult, ...]:
    if mode_unsupported or mode != "wal":
        return (
            CheckResult("wal-mode-active", "UNSUPPORTED", "UNSUPPORTED_WAL_MODE"),
            CheckResult("wal-file-present", "UNSUPPORTED", "UNSUPPORTED_WAL_MODE"),
            CheckResult("wal-file-nonempty", "UNSUPPORTED", "UNSUPPORTED_WAL_MODE"),
            CheckResult("wal-control-marker-present", "UNSUPPORTED", "UNSUPPORTED_WAL_MODE"),
            CheckResult("wal-marker-absent", "UNSUPPORTED", "UNSUPPORTED_WAL_MODE"),
            CheckResult("wal-encrypted-content", "UNSUPPORTED", "UNSUPPORTED_WAL_MODE"),
        )
    present = wal_exists
    nonempty = present and wal_size > 0
    control = nonempty and control_marker_present
    absent = control and not encrypted_marker_present
    encrypted = present and nonempty and control and absent
    return (
        CheckResult("wal-mode-active", "PASS", "PASS"),
        CheckResult(
            "wal-file-present",
            "PASS" if present else "FAIL",
            "PASS" if present else "ERR_WAL_NOT_CREATED",
        ),
        CheckResult(
            "wal-file-nonempty",
            "PASS" if nonempty else "FAIL",
            "PASS" if nonempty else ("ERR_WAL_EMPTY" if present else "ERR_WAL_NOT_CREATED"),
            wal_size,
        ),
        CheckResult(
            "wal-control-marker-present",
            "PASS" if control else "FAIL",
            "PASS" if control else "ERR_WAL_CONTROL_MARKER_MISSING",
        ),
        CheckResult(
            "wal-marker-absent",
            "PASS" if absent else "FAIL",
            "PASS"
            if absent
            else (
                "ERR_MARKER_IN_WAL"
                if encrypted_marker_present
                else "ERR_WAL_CONTROL_MARKER_MISSING"
            ),
        ),
        CheckResult(
            "wal-encrypted-content",
            "PASS" if encrypted else "FAIL",
            "PASS"
            if encrypted
            else (
                "ERR_MARKER_IN_WAL"
                if encrypted_marker_present
                else (
                    "ERR_WAL_CONTROL_MARKER_MISSING"
                    if nonempty
                    else ("ERR_WAL_EMPTY" if present else "ERR_WAL_NOT_CREATED")
                )
            ),
        ),
    )


def _journal_checks_from_evidence(
    *,
    mode: str,
    journal_exists: bool,
    journal_size: int,
    control_marker_present: bool,
    encrypted_marker_present: bool,
    mode_unsupported: bool = False,
) -> tuple[CheckResult, ...]:
    active = mode in {"delete", "truncate", "persist"}
    if mode_unsupported or not active:
        return (
            CheckResult("journal-mode-active", "UNSUPPORTED", "UNSUPPORTED_ROLLBACK_JOURNAL_MODE"),
            CheckResult("journal-file-present", "UNSUPPORTED", "UNSUPPORTED_ROLLBACK_JOURNAL_MODE"),
            CheckResult(
                "journal-file-nonempty", "UNSUPPORTED", "UNSUPPORTED_ROLLBACK_JOURNAL_MODE"
            ),
            CheckResult(
                "journal-control-marker-present", "UNSUPPORTED", "UNSUPPORTED_ROLLBACK_JOURNAL_MODE"
            ),
            CheckResult(
                "journal-marker-absent", "UNSUPPORTED", "UNSUPPORTED_ROLLBACK_JOURNAL_MODE"
            ),
        )
    present = journal_exists
    nonempty = present and journal_size > 0
    control = nonempty and control_marker_present
    absent = control and not encrypted_marker_present
    return (
        CheckResult("journal-mode-active", "PASS", "PASS"),
        CheckResult(
            "journal-file-present",
            "PASS" if present else "FAIL",
            "PASS" if present else "ERR_JOURNAL_NOT_CREATED",
        ),
        CheckResult(
            "journal-file-nonempty",
            "PASS" if nonempty else "FAIL",
            "PASS" if nonempty else ("ERR_JOURNAL_EMPTY" if present else "ERR_JOURNAL_NOT_CREATED"),
            journal_size,
        ),
        CheckResult(
            "journal-control-marker-present",
            "PASS" if control else "FAIL",
            "PASS" if control else "ERR_JOURNAL_CONTROL_MARKER_MISSING",
        ),
        CheckResult(
            "journal-marker-absent",
            "PASS" if absent else "FAIL",
            "PASS"
            if absent
            else (
                "ERR_MARKER_IN_JOURNAL"
                if encrypted_marker_present
                else "ERR_JOURNAL_CONTROL_MARKER_MISSING"
            ),
        ),
    )


def _run_wal_evidence(
    sqlcipher3: Any, temp_dir: Path, key: bytes, marker: bytes
) -> tuple[CheckResult, ...]:
    payload = _marker_payload(marker)
    db_path = temp_dir / "wal-probe.db"
    wal_path = db_path.with_name(db_path.name + "-wal")
    conn = None
    try:
        conn = sqlcipher3.connect(str(db_path))
        _key_connection(conn, key)
        rows = list(conn.execute("PRAGMA journal_mode=WAL").fetchall())
        mode = _mode_from_rows(rows)
        if mode != "wal":
            return _wal_checks_from_evidence(
                mode=mode,
                wal_exists=False,
                wal_size=0,
                control_marker_present=False,
                encrypted_marker_present=False,
                mode_unsupported=True,
            )
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("CREATE TABLE synthetic_wal(id INTEGER PRIMARY KEY, value BLOB)")
        conn.commit()
        conn.execute("INSERT INTO synthetic_wal(value) VALUES (?)", (payload,))
        conn.commit()
        exists = wal_path.exists()
        size = wal_path.stat().st_size if exists else 0
        encrypted_has = exists and marker in wal_path.read_bytes()
        control = _ordinary_wal_control(temp_dir, payload, marker)
        return _wal_checks_from_evidence(
            mode=mode,
            wal_exists=exists,
            wal_size=size,
            control_marker_present=control,
            encrypted_marker_present=encrypted_has,
        )
    except Exception:
        return (
            CheckResult("wal-mode-active", "FAIL", "ERR_WAL_PROBE_FAILED"),
            CheckResult("wal-file-present", "FAIL", "ERR_WAL_PROBE_FAILED"),
            CheckResult("wal-file-nonempty", "FAIL", "ERR_WAL_PROBE_FAILED"),
            CheckResult("wal-control-marker-present", "FAIL", "ERR_WAL_PROBE_FAILED"),
            CheckResult("wal-marker-absent", "FAIL", "ERR_WAL_PROBE_FAILED"),
            CheckResult("wal-encrypted-content", "FAIL", "ERR_WAL_PROBE_FAILED"),
        )
    finally:
        if conn is not None:
            conn.close()


def _ordinary_wal_control(temp_dir: Path, payload: bytes, marker: bytes) -> bool:
    db_path = temp_dir / "wal-control.db"
    wal_path = db_path.with_name(db_path.name + "-wal")
    conn = sqlite3.connect(db_path)
    try:
        mode = str(conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
        if mode != "wal":
            return False
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("CREATE TABLE synthetic_wal(id INTEGER PRIMARY KEY, value BLOB)")
        conn.commit()
        conn.execute("INSERT INTO synthetic_wal(value) VALUES (?)", (payload,))
        conn.commit()
        return wal_path.exists() and wal_path.stat().st_size > 0 and marker in wal_path.read_bytes()
    finally:
        conn.close()


def _run_journal_evidence(
    sqlcipher3: Any, temp_dir: Path, key: bytes, marker: bytes
) -> tuple[CheckResult, ...]:
    original = _marker_payload(marker)
    replacement = _marker_payload(b"synthetic-replacement-")
    db_path = temp_dir / "journal-probe.db"
    journal_path = db_path.with_name(db_path.name + "-journal")
    conn = None
    transaction_active = False
    try:
        conn = sqlcipher3.connect(str(db_path))
        _key_connection(conn, key)
        rows = list(conn.execute("PRAGMA journal_mode=DELETE").fetchall())
        mode = _mode_from_rows(rows)
        if mode not in {"delete", "truncate", "persist"}:
            return _journal_checks_from_evidence(
                mode=mode,
                journal_exists=False,
                journal_size=0,
                control_marker_present=False,
                encrypted_marker_present=False,
                mode_unsupported=True,
            )
        conn.execute("CREATE TABLE synthetic_journal(id INTEGER PRIMARY KEY, value BLOB)")
        conn.execute("INSERT INTO synthetic_journal(value) VALUES (?)", (original,))
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        transaction_active = True
        conn.execute("UPDATE synthetic_journal SET value=? WHERE id=1", (replacement,))
        exists = journal_path.exists()
        size = journal_path.stat().st_size if exists else 0
        encrypted_has = exists and marker in journal_path.read_bytes()
        control = _ordinary_journal_control(temp_dir, original, replacement, marker)
        return _journal_checks_from_evidence(
            mode=mode,
            journal_exists=exists,
            journal_size=size,
            control_marker_present=control,
            encrypted_marker_present=encrypted_has,
        )
    except Exception:
        return (
            CheckResult("journal-mode-active", "FAIL", "ERR_JOURNAL_PROBE_FAILED"),
            CheckResult("journal-file-present", "FAIL", "ERR_JOURNAL_PROBE_FAILED"),
            CheckResult("journal-file-nonempty", "FAIL", "ERR_JOURNAL_PROBE_FAILED"),
            CheckResult("journal-control-marker-present", "FAIL", "ERR_JOURNAL_PROBE_FAILED"),
            CheckResult("journal-marker-absent", "FAIL", "ERR_JOURNAL_PROBE_FAILED"),
        )
    finally:
        if conn is not None:
            try:
                if transaction_active:
                    conn.rollback()
            finally:
                conn.close()


def _ordinary_journal_control(
    temp_dir: Path, original: bytes, replacement: bytes, marker: bytes
) -> bool:
    db_path = temp_dir / "journal-control.db"
    journal_path = db_path.with_name(db_path.name + "-journal")
    conn = sqlite3.connect(db_path)
    active = False
    try:
        mode = str(conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0]).lower()
        if mode not in {"delete", "truncate", "persist"}:
            return False
        conn.execute("CREATE TABLE synthetic_journal(id INTEGER PRIMARY KEY, value BLOB)")
        conn.execute("INSERT INTO synthetic_journal(value) VALUES (?)", (original,))
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        active = True
        conn.execute("UPDATE synthetic_journal SET value=? WHERE id=1", (replacement,))
        return (
            journal_path.exists()
            and journal_path.stat().st_size > 0
            and marker in journal_path.read_bytes()
        )
    finally:
        try:
            if active:
                conn.rollback()
        finally:
            conn.close()


def run_sqlcipher_probe(temp_dir: Path) -> SqlcipherEvidence:
    if platform.system() != "Windows":
        return SqlcipherEvidence(
            status="UNSUPPORTED",
            checks=(CheckResult("sqlcipher-overall", "UNSUPPORTED", "UNSUPPORTED_NON_WINDOWS"),),
        )
    try:
        sqlcipher3 = cast(Any, importlib.import_module("sqlcipher3"))
    except ImportError:
        return SqlcipherEvidence(
            status="UNSUPPORTED",
            raw_key_api_assessment="UNAVAILABLE",
            checks=(CheckResult("sqlcipher-overall", "UNSUPPORTED", "ERR_SQLCIPHER_IMPORT"),),
        )

    temp_dir.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    wrong = os.urandom(32)
    marker = SYNTHETIC_MARKER_PREFIX + os.urandom(16)
    db_path = temp_dir / "probe.db"
    checks: list[CheckResult] = []
    startup = time.perf_counter_ns()
    conn = sqlcipher3.connect(str(db_path))
    startup_ms = (time.perf_counter_ns() - startup) // 1_000_000
    cipher_status_value = "UNSUPPORTED"
    integrity_result = "UNSUPPORTED"
    sqlcipher_version = "UNSUPPORTED"
    sqlite_version = "UNSUPPORTED"
    journal_mode = "UNSUPPORTED"
    temp_store = "UNSUPPORTED"
    compile_options: tuple[str, ...] = ()
    crypto_provider = "UNSUPPORTED"
    logging_status = "UNSUPPORTED"
    hmac_evidence = "NOT_DEMONSTRATED"
    wal_evidence = "NOT_DEMONSTRATED"
    journal_evidence = "NOT_DEMONSTRATED"
    try:
        _key_connection(conn, key)
        checks.append(CheckResult("sqlcipher-startup", "PASS", "PASS", startup_ms))
        status, rows = _execute_pragma(conn, "PRAGMA cipher_status")
        cipher_status_value, cs_check = _cipher_status_check(status, rows)
        checks.append(cs_check)
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value BLOB)")
        conn.execute("CREATE INDEX ix_t_value ON t(value)")
        conn.execute("INSERT INTO t(value) VALUES (?)", (marker,))
        conn.commit()
        status, rows = _execute_pragma(conn, "PRAGMA cipher_version")
        if status == "PASS" and rows:
            sqlcipher_version = str(rows[0][0])
        status, rows = _execute_pragma(conn, "select sqlite_version()")
        if status == "PASS" and rows:
            sqlite_version = str(rows[0][0])
        status, rows = _execute_pragma(conn, "PRAGMA cipher_integrity_check")
        integrity_result, ci_check = _cipher_integrity_check(status, rows)
        checks.append(ci_check)
        status, rows = _execute_pragma(conn, "PRAGMA compile_options")
        compile_options = tuple(str(row[0]) for row in rows) if status == "PASS" else ()
        for pragma in ("PRAGMA cipher_provider", "PRAGMA cipher_provider_version"):
            status, rows = _execute_pragma(conn, pragma)
            if status == "PASS" and rows:
                crypto_provider = str(rows[0][0])
                break
        for pragma_valid in ("PRAGMA cipher_hmac_pgno", "PRAGMA cipher_hmac_algorithm"):
            _, hmac_rows = _execute_pragma(conn, pragma_valid)
            if hmac_rows:
                hmac_evidence = "AVAILABLE"
        status, rows = _execute_pragma(conn, "PRAGMA cipher_log_level")
        logging_status = status
        conn.execute("PRAGMA journal_mode=WAL")
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0])
        temp_store = str(conn.execute("PRAGMA temp_store").fetchone()[0])
    finally:
        conn.close()

    created_check, main_bytes = _read_created_db(db_path)
    checks.append(created_check)
    if main_bytes is None:
        return SqlcipherEvidence(
            status="FAIL",
            binding_version=importlib.metadata.version("sqlcipher3"),
            cipher_status=cipher_status_value,
            integrity_result=integrity_result,
            sqlcipher_version=sqlcipher_version,
            sqlite_version=sqlite_version,
            journal_mode=journal_mode,
            temp_store=temp_store,
            compile_options=compile_options,
            cryptographic_provider=crypto_provider,
            logging_status=logging_status,
            hmac_evidence=hmac_evidence,
            wal_evidence=wal_evidence,
            journal_evidence=journal_evidence,
            raw_key_api_assessment=inspect_raw_key_api(sqlcipher3),
            checks=tuple(checks),
        )

    checks.extend(
        [
            _status_from_bool(
                "encrypted-main-header",
                b"SQLite format 3" not in main_bytes[:100],
                "ERR_PLAINTEXT_HEADER",
            ),
            _status_from_bool("main-marker-absent", marker not in main_bytes, "ERR_MARKER_IN_DB"),
            _status_from_bool(
                "temp-store-memory",
                temp_store in {"2", "MEMORY", "memory"},
                "ERR_TEMP_STORE_NOT_MEMORY",
            ),
        ]
    )

    correct_conn = sqlcipher3.connect(str(db_path))
    try:
        _key_connection(correct_conn, key)
        row = correct_conn.execute("SELECT value FROM t WHERE id=1").fetchone()
        if row is None or row[0] != marker:
            checks.append(
                CheckResult("correct-key-query", "FAIL", "ERR_CORRECT_KEY_MARKER_MISMATCH")
            )
        else:
            checks.append(CheckResult("correct-key-query", "PASS", "PASS"))
    except Exception:
        checks.append(CheckResult("correct-key-query", "FAIL", "ERR_CORRECT_KEY_EXCEPTION"))
    finally:
        correct_conn.close()

    wrong_conn = sqlcipher3.connect(str(db_path))
    try:
        _key_connection(wrong_conn, wrong)
        wrong_conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        wrong_key = False
    except Exception:
        wrong_key = True
    finally:
        wrong_conn.close()
    checks.append(_status_from_bool("wrong-key-query", wrong_key, "ERR_WRONG_KEY_ACCEPTED"))

    ordinary_fails = _ordinary_sqlite_rejects(db_path)
    checks.append(
        _status_from_bool("ordinary-sqlite-failure", ordinary_fails, "ERR_SQLITE_ACCEPTED")
    )

    try:
        bit_detected = _corruption_detected(sqlcipher3, db_path, key, "bit")
    except Exception:
        bit_detected = False
    checks.append(
        _status_from_bool(
            "bit-modified-detection",
            bit_detected,
            "ERR_BIT_TAMPER_UNDETECTED",
        )
    )

    try:
        trunc_detected = _corruption_detected(sqlcipher3, db_path, key, "truncate")
    except Exception:
        trunc_detected = False
    checks.append(
        _status_from_bool(
            "truncated-detection",
            trunc_detected,
            "ERR_TRUNCATION_UNDETECTED",
        )
    )

    wal_checks = _run_wal_evidence(sqlcipher3, temp_dir, key, marker)
    checks.extend(wal_checks)
    wal_evidence = "PRESENT" if all(check.status == "PASS" for check in wal_checks) else "FAILED"

    journal_checks = _run_journal_evidence(sqlcipher3, temp_dir, key, marker)
    checks.extend(journal_checks)
    journal_evidence = (
        "PRESENT" if all(check.status == "PASS" for check in journal_checks) else "FAILED"
    )

    controlled_files = [path for path in temp_dir.rglob("*") if path.is_file()]
    checks.append(
        _status_from_bool(
            "controlled-temp-scan",
            _scan_for_marker(controlled_files, marker),
            "ERR_MARKER_IN_TEMP",
        )
    )

    cleanup_ok = True
    try:
        for f in temp_dir.rglob("*"):
            if f.is_file():
                f.unlink()
    except OSError:
        cleanup_ok = False
    checks.append(_status_from_bool("connection-cleanup", cleanup_ok, "ERR_CLEANUP_FAILED"))

    mandatory_failed = any(check.status == "FAIL" for check in checks)
    missing_mandatory = cipher_status_value != "1" or integrity_result not in {
        "PASS",
        "UNSUPPORTED",
    }
    return SqlcipherEvidence(
        status="FAIL" if mandatory_failed or missing_mandatory else "PASS",
        binding_version=importlib.metadata.version("sqlcipher3"),
        sqlcipher_version=sqlcipher_version,
        sqlite_version=sqlite_version,
        cipher_status=cipher_status_value,
        integrity_result=integrity_result,
        compile_options=compile_options,
        cryptographic_provider=crypto_provider,
        journal_mode=journal_mode,
        temp_store=temp_store,
        raw_key_api_assessment=inspect_raw_key_api(sqlcipher3),
        logging_status=logging_status,
        hmac_evidence=hmac_evidence,
        wal_evidence=wal_evidence,
        journal_evidence=journal_evidence,
        checks=tuple(checks),
    )


def run_standard_sqlite_performance() -> list[CheckResult]:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "standard.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value BLOB)")
            start = time.perf_counter_ns()
            conn.execute("INSERT INTO t(value) VALUES (?)", (os.urandom(32),))
            conn.commit()
            insert_ms = (time.perf_counter_ns() - start) // 1_000_000
            start = time.perf_counter_ns()
            conn.execute("SELECT count(*) FROM t WHERE id >= 0").fetchone()
            read_ms = (time.perf_counter_ns() - start) // 1_000_000
        finally:
            conn.close()
    return [
        CheckResult("sqlite-insert-transaction", "PASS", "PASS", insert_ms),
        CheckResult("sqlite-indexed-read", "PASS", "PASS", read_ms),
    ]
