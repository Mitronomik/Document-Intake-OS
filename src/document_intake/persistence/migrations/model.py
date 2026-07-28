"""Migration model."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, Literal

APPLICATION_ID = 0x44494F53
MigrationForeignKeyMode = Literal["ENFORCED", "DISABLED_DURING_TABLE_REBUILD"]


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]
    checksum: str
    foreign_key_mode: MigrationForeignKeyMode = "ENFORCED"
    transform_id: str | None = None
    transform_after_statement: int | None = None
    transform: Callable[[Any], None] | None = dataclass_field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        configured = (
            self.transform_id is not None,
            self.transform_after_statement is not None,
            self.transform is not None,
        )
        if any(configured) != all(configured):
            raise ValueError("migration.transform: incomplete")
        if self.transform_id is not None and (
            not self.transform_id
            or self.transform_after_statement not in range(len(self.statements))
        ):
            raise ValueError("migration.transform: invalid")


def migration_checksum(
    statements: tuple[str, ...],
    *,
    foreign_key_mode: MigrationForeignKeyMode = "ENFORCED",
    transform_id: str | None = None,
    transform_after_statement: int | None = None,
) -> str:
    canonical = "\n-- statement --\n".join(statement.strip() for statement in statements)
    if foreign_key_mode == "DISABLED_DURING_TABLE_REBUILD":
        canonical += "\n-- migration foreign key mode --\nDISABLED_DURING_TABLE_REBUILD"
    if (transform_id is None) != (transform_after_statement is None):
        raise ValueError("migration transform checksum identity is incomplete")
    if transform_id is not None:
        canonical += f"\n-- migration transform --\n{transform_id}@{transform_after_statement}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
