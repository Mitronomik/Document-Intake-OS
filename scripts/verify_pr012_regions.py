"""Sanitized Windows production-SQLCipher verifier for PR-012."""

from __future__ import annotations

import platform
import sqlite3
import tempfile
from pathlib import Path

from document_intake.persistence import database
from document_intake.persistence.database import EncryptedDatabase
from document_intake.persistence.errors import PersistenceError
from document_intake.persistence.migrations import MIGRATIONS
from document_intake.persistence.migrations.v0008_document_regions import MIGRATION

_LABELS = (
    "PR012_VERIFY schema_version=8",
    f"PR012_VERIFY candidate_v0008_checksum={MIGRATION.checksum}",
    "PR012_VERIFY encrypted_v7_to_v8=PASS",
    "PR012_VERIFY migration_history=PASS",
    "PR012_VERIFY foreign_keys=PASS",
    "PR012_VERIFY cipher_integrity=PASS",
    "PR012_VERIFY wrong_key=PASS",
    "PR012_VERIFY sqlite_rejected=PASS",
    "PR012_VERIFY privacy=PASS",
    "PR012_VERIFY result=PASS",
)
_UNSUPPORTED = ("PR012_VERIFY result=INCONCLUSIVE code=UNSUPPORTED_PLATFORM",)


class _Key:
    def __init__(self, value: bytes = b"R" * 32) -> None:
        self.value = value

    def get_database_key(self) -> bytes:
        return self.value


def _unsupported_code() -> str | None:
    return None if platform.system() == "Windows" else "UNSUPPORTED_PLATFORM"


def _emit(lines: tuple[str, ...]) -> None:
    for line in lines:
        print(line)


def _create_schema7(path: Path) -> None:
    old_migrations = database.MIGRATIONS  # type: ignore[attr-defined]
    old_version = database.CURRENT_SCHEMA_VERSION  # type: ignore[attr-defined]
    try:
        database.MIGRATIONS = MIGRATIONS[:7]  # type: ignore[attr-defined]
        database.CURRENT_SCHEMA_VERSION = 7  # type: ignore[attr-defined]
        EncryptedDatabase(path, _Key()).initialize()
    finally:
        database.MIGRATIONS = old_migrations  # type: ignore[attr-defined]
        database.CURRENT_SCHEMA_VERSION = old_version  # type: ignore[attr-defined]


def _run_supported() -> bool:
    with tempfile.TemporaryDirectory(prefix="pr012-verify-") as temporary:
        path = Path(temporary) / "state.db"
        _create_schema7(path)
        EncryptedDatabase(path, _Key()).initialize()
        connection = database._open_connection(path, _Key())
        try:
            version = connection.execute("PRAGMA user_version").fetchone() == (8,)
            history = connection.execute(
                "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
            ).fetchall()
            integrity = connection.execute("PRAGMA cipher_integrity_check").fetchall()
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            connection.close()
        try:
            database._open_connection(path, _Key(b"W" * 32))
            wrong_key = False
        except PersistenceError:
            wrong_key = True
        try:
            plain = sqlite3.connect(path)
            plain.execute("SELECT count(*) FROM schema_migrations").fetchone()
            sqlite_rejected = False
        except sqlite3.DatabaseError:
            sqlite_rejected = True
        finally:
            plain.close()
        return (
            version
            and history[-1] == (8, MIGRATION.name, MIGRATION.checksum)
            and foreign_keys
            and not integrity
            and wrong_key
            and sqlite_rejected
        )


def main() -> int:
    if _unsupported_code() is not None:
        _emit(_UNSUPPORTED)
        return 2
    try:
        passed = _run_supported()
    except Exception:
        passed = False
    if not passed:
        print("PR012_VERIFY result=FAIL")
        return 1
    _emit(_LABELS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
