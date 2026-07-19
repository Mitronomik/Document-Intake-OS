"""Forward-only migrations."""

from document_intake.persistence.migrations.model import (
    APPLICATION_ID,
    Migration,
    migration_checksum,
)
from document_intake.persistence.migrations.v0001_initial import MIGRATION as V0001_INITIAL
from document_intake.persistence.migrations.v0002_stored_artifacts import MIGRATION as V0002_STORED_ARTIFACTS
from document_intake.persistence.migrations.v0002_stored_artifacts import MIGRATION as V0002_STORED_ARTIFACTS

MIGRATIONS: tuple[Migration, ...] = (V0001_INITIAL, V0002_STORED_ARTIFACTS)
CURRENT_SCHEMA_VERSION = 2

__all__ = [
    "APPLICATION_ID",
    "CURRENT_SCHEMA_VERSION",
    "MIGRATIONS",
    "Migration",
    "migration_checksum",
]
