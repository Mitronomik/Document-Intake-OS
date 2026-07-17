from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OfflineSmokeResult:
    status: str
    sqlcipher_version: str = "UNSUPPORTED"
    cleanup_status: str = "NOT_DEMONSTRATED"


def _raw_key_fragment(key: bytes) -> str:
    return "x'" + key.hex() + "'"


def run_offline_smoke() -> OfflineSmokeResult:
    temp_dir = Path(tempfile.mkdtemp(prefix="pr-s001-offline-"))
    try:
        try:
            import sqlcipher3  # type: ignore[import-not-found]
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            return OfflineSmokeResult("UNSUPPORTED_DEPENDENCY_MISSING")
        key = os.urandom(32)
        wrong = os.urandom(32)
        db_path = temp_dir / "offline.db"
        conn = sqlcipher3.connect(str(db_path))
        try:
            conn.execute("PRAGMA key = " + _raw_key_fragment(key))
            conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value BLOB)")
            conn.execute("INSERT INTO t(value) VALUES (?)", (os.urandom(32),))
            conn.commit()
            version = str(conn.execute("PRAGMA cipher_version").fetchone()[0])
        finally:
            conn.close()
        correct = sqlcipher3.connect(str(db_path))
        try:
            correct.execute("PRAGMA key = " + _raw_key_fragment(key))
            correct.execute("SELECT count(*) FROM sqlite_master").fetchone()
        finally:
            correct.close()
        wrong_conn = sqlcipher3.connect(str(db_path))
        try:
            wrong_conn.execute("PRAGMA key = " + _raw_key_fragment(wrong))
            wrong_conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
            return OfflineSmokeResult("FAIL_WRONG_KEY_ACCEPTED", version)
        except Exception:
            pass
        finally:
            wrong_conn.close()
        try:
            sqlite3.connect(db_path).execute("SELECT count(*) FROM sqlite_master").fetchone()
            return OfflineSmokeResult("FAIL_ORDINARY_SQLITE_ACCEPTED", version)
        except sqlite3.DatabaseError:
            pass
        aes = AESGCM(os.urandom(32))
        nonce = os.urandom(12)
        data = os.urandom(64)
        if aes.decrypt(nonce, aes.encrypt(nonce, data, b"aad"), b"aad") != data:
            return OfflineSmokeResult("FAIL_AES_GCM", version)
        return OfflineSmokeResult("PASS", version, "PENDING_CLEANUP")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def offline_environment_note() -> str:
    if platform.system() == "Windows":
        return "WHEELHOUSE_NO_INDEX_FIND_LINKS_SMOKE_ONLY"
    return "UNSUPPORTED_NON_WINDOWS"


def main() -> int:
    result = run_offline_smoke()
    print(result.status)
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
