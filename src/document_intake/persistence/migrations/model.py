"""Migration model."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

APPLICATION_ID = 0x44494F53
MigrationForeignKeyMode = Literal["ENFORCED", "DISABLED_DURING_TABLE_REBUILD"]


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]
    checksum: str
    foreign_key_mode: MigrationForeignKeyMode = "ENFORCED"


def migration_checksum(
    statements: tuple[str, ...], *, foreign_key_mode: MigrationForeignKeyMode = "ENFORCED"
) -> str:
    canonical = "\n-- statement --\n".join(statement.strip() for statement in statements)
    if foreign_key_mode == "DISABLED_DURING_TABLE_REBUILD":
        canonical += "\n-- migration foreign key mode --\nDISABLED_DURING_TABLE_REBUILD"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
