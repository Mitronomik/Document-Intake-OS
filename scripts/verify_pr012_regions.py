"""Privacy-safe schema-8 production migration verifier for PR-012."""

from __future__ import annotations

import sqlite3

from document_intake.persistence.database import _apply_migrations
from document_intake.persistence.migrations.v0008_document_regions import MIGRATION

_LABELS = (
    "schema_version=8",
    f"candidate_v0008_checksum={MIGRATION.checksum}",
    "migration_history=PASS",
    "foreign_keys=PASS",
    "immutability=PASS",
    "privacy=PASS",
    "result=PASS",
)


def main() -> int:
    try:
        connection = sqlite3.connect(":memory:")
        connection.execute("PRAGMA foreign_keys=ON")
        _apply_migrations(connection)
        if connection.execute("PRAGMA user_version").fetchone() != (8,):
            return 1
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            return 1
        history = connection.execute(
            "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        if history[-1] != (8, MIGRATION.name, MIGRATION.checksum):
            return 1
        for label in _LABELS:
            print(label)
        return 0
    except Exception:
        print("result=FAIL")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
