"""Migration model."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

APPLICATION_ID = 0x44494F53


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]
    checksum: str


def migration_checksum(statements: tuple[str, ...]) -> str:
    canonical = "\n-- statement --\n".join(statement.strip() for statement in statements)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
