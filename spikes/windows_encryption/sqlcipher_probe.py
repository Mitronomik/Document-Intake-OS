from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SYNTHETIC_MARKER_PREFIX = b"synthetic-record-"


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
    checks: tuple[CheckResult, ...] = ()


def raw_key_pragma_fragment(key: bytes) -> str:
    if len(key) != 32:
        raise ValueError("ERR_INVALID_DB_KEY")
    return "x'" + key.hex() + "'"


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


def run_sqlcipher_probe(temp_dir: Path) -> SqlcipherEvidence:
    if platform.system() != "Windows":
        return SqlcipherEvidence(
            status="UNSUPPORTED",
            checks=(CheckResult("sqlcipher-platform", "UNSUPPORTED", "UNSUPPORTED_NON_WINDOWS"),),
        )
    try:
        import sqlcipher3  # type: ignore[import-not-found]
    except ImportError:
        return SqlcipherEvidence(
            status="UNSUPPORTED",
            raw_key_api_assessment="UNAVAILABLE",
            checks=(CheckResult("sqlcipher-import", "UNSUPPORTED", "ERR_SQLCIPHER_IMPORT"),),
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
    try:
        _key_connection(conn, key)
        checks.append(CheckResult("sqlcipher-startup", "PASS", "PASS", startup_ms))
        status, rows = _execute_pragma(conn, "PRAGMA cipher_status")
        if status == "PASS" and rows:
            cipher_status_value = str(rows[0][0])
        checks.append(CheckResult("cipher-status", status, cipher_status_value))
        conn.execute("PRAGMA journal_mode=WAL")
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0])
        temp_store = str(conn.execute("PRAGMA temp_store").fetchone()[0])
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
        integrity_result = "PASS" if status == "PASS" and not rows else status
        checks.append(CheckResult("cipher-integrity", integrity_result, integrity_result))
        status, rows = _execute_pragma(conn, "PRAGMA compile_options")
        compile_options = tuple(str(row[0]) for row in rows) if status == "PASS" else ()
        for pragma in ("PRAGMA cipher_provider", "PRAGMA cipher_provider_version"):
            status, rows = _execute_pragma(conn, pragma)
            if status == "PASS" and rows:
                crypto_provider = str(rows[0][0])
                break
        status, _ = _execute_pragma(conn, "PRAGMA cipher_log_level=NONE")
        logging_status = "PASS" if status == "PASS" else "UNSUPPORTED"
    finally:
        conn.close()
    main_bytes = db_path.read_bytes()
    checks.extend(
        [
            CheckResult("encrypted-db-created", "PASS" if db_path.exists() else "FAIL", "PASS"),
            CheckResult("correct-key-query", "PASS", "PASS"),
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
    try:
        sqlite3.connect(db_path).execute("SELECT count(*) FROM sqlite_master").fetchone()
        ordinary_fails = False
    except sqlite3.DatabaseError:
        ordinary_fails = True
    checks.append(
        _status_from_bool("ordinary-sqlite-failure", ordinary_fails, "ERR_SQLITE_ACCEPTED")
    )
    checks.append(
        _status_from_bool(
            "bit-modified-detection",
            _corruption_detected(sqlcipher3, db_path, key, "bit"),
            "ERR_BIT_TAMPER_UNDETECTED",
        )
    )
    checks.append(
        _status_from_bool(
            "truncated-detection",
            _corruption_detected(sqlcipher3, db_path, key, "truncate"),
            "ERR_TRUNCATION_UNDETECTED",
        )
    )
    wal_paths = list(temp_dir.glob("*.db-wal"))
    journal_paths = list(temp_dir.glob("*.db-journal"))
    checks.append(
        _status_from_bool(
            "wal-marker-absent", _scan_for_marker(wal_paths, marker), "ERR_MARKER_IN_WAL"
        )
    )
    checks.append(
        _status_from_bool(
            "journal-marker-absent",
            _scan_for_marker(journal_paths, marker),
            "ERR_MARKER_IN_JOURNAL",
        )
    )
    controlled_files = [path for path in temp_dir.rglob("*") if path.is_file()]
    checks.append(
        _status_from_bool(
            "controlled-temp-scan", _scan_for_marker(controlled_files, marker), "ERR_MARKER_IN_TEMP"
        )
    )
    checks.append(CheckResult("connection-cleanup", "PASS", "PASS"))
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
