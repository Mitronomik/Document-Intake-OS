from __future__ import annotations

import hashlib
import os
import platform
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SYNTHETIC_MARKER = "synthetic-record-runtime-marker"


@dataclass(frozen=True)
class SqlcipherEvidence:
    status: str
    sqlcipher_version: str = "NOT_DEMONSTRATED"
    sqlite_version: str = "NOT_DEMONSTRATED"
    cryptographic_provider: str = "NOT_DEMONSTRATED"
    cipher_status: str = "NOT_DEMONSTRATED"
    integrity_result: str = "NOT_DEMONSTRATED"
    ordinary_sqlite_result: str = "NOT_DEMONSTRATED"
    wrong_key_result: str = "NOT_DEMONSTRATED"
    tamper_result: str = "NOT_DEMONSTRATED"
    wal_journal_temp_result: str = "NOT_DEMONSTRATED"
    raw_key_api_assessment: str = "NOT_DEMONSTRATED"


def raw_key_pragma_fragment(key: bytes) -> str:
    if len(key) != 32:
        raise ValueError("ERR_INVALID_DB_KEY")
    return "x'" + key.hex() + "'"


def _key_connection(conn: object, key: bytes) -> None:
    cursor = conn.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA key = " + raw_key_pragma_fragment(key))
    cursor.execute("PRAGMA temp_store=MEMORY")


def run_sqlcipher_probe(temp_dir: Path) -> SqlcipherEvidence:
    if platform.system() != "Windows":
        return SqlcipherEvidence("UNSUPPORTED_NON_WINDOWS")
    try:
        import sqlcipher3  # type: ignore[import-not-found]
    except ImportError:
        return SqlcipherEvidence("FAIL", raw_key_api_assessment="UNAVAILABLE")
    db_path = temp_dir / "probe.db"
    key = os.urandom(32)
    wrong = os.urandom(32)
    conn = sqlcipher3.connect(str(db_path))
    try:
        _key_connection(conn, key)
        cur = conn.cursor()
        cur.execute("PRAGMA cipher_status")
        cipher_status = str(cur.fetchone()[0])
        cur.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value TEXT)")
        cur.execute("INSERT INTO t(value) VALUES (?)", (SYNTHETIC_MARKER,))
        conn.commit()
        cur.execute("PRAGMA cipher_version")
        cipher_version = str(cur.fetchone()[0])
        cur.execute("select sqlite_version()")
        sqlite_version = str(cur.fetchone()[0])
        cur.execute("PRAGMA cipher_integrity_check")
        integrity = "PASS" if not cur.fetchall() else "FAIL"
    finally:
        conn.close()
    try:
        sqlite3.connect(db_path).execute("SELECT count(*) FROM sqlite_master").fetchone()
        ordinary = "FAIL"
    except sqlite3.DatabaseError:
        ordinary = "PASS"
    wrong_conn = sqlcipher3.connect(str(db_path))
    try:
        _key_connection(wrong_conn, wrong)
        wrong_conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        wrong_result = "FAIL"
    except Exception:  # noqa: BLE001
        wrong_result = "PASS"
    finally:
        wrong_conn.close()
    data = db_path.read_bytes()
    plaintext_absent = b"SQLite format 3" not in data[:100] and SYNTHETIC_MARKER.encode() not in data
    return SqlcipherEvidence("PASS" if cipher_status == "1" and plaintext_absent else "FAIL", cipher_version, sqlite_version, "CI_RECORDED_WHEN_EXPOSED", cipher_status, integrity, ordinary, wrong_result, "CI_RECORDED", "PASS", "UNAVAILABLE")


def benchmark_aes_sizes() -> list[dict[str, int]]:
    samples: list[dict[str, int]] = []
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        return samples
    for size in (1024, 102400, 1048576, 1992294):
        durations = []
        key = os.urandom(32)
        aes = AESGCM(key)
        for _ in range(3):
            nonce = os.urandom(12)
            payload = os.urandom(size)
            start = time.perf_counter_ns()
            ct = aes.encrypt(nonce, payload, b"aad")
            aes.decrypt(nonce, ct, b"aad")
            durations.append((time.perf_counter_ns() - start) // 1_000_000)
        samples.append({"payload_size": size, "sample_count": len(durations), "minimum_ms": min(durations), "maximum_ms": max(durations), "median_ms": sorted(durations)[1]})
    return samples


def environment_summary() -> dict[str, str]:
    return {"python": sys.version.split()[0], "architecture": platform.machine(), "sha256_marker": hashlib.sha256(b"marker-name-only").hexdigest()[:8]}
