"""Forward-only migrations."""

from document_intake.persistence.migrations.model import (
    APPLICATION_ID,
    Migration,
    migration_checksum,
)
from document_intake.persistence.migrations.v0001_initial import MIGRATION as V0001_INITIAL

MIGRATIONS: tuple[Migration, ...] = (V0001_INITIAL,)
CURRENT_SCHEMA_VERSION = 1

__all__ = [
    "APPLICATION_ID",
    "CURRENT_SCHEMA_VERSION",
    "MIGRATIONS",
    "Migration",
    "migration_checksum",
]
