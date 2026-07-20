"""Forward-only migrations."""

from document_intake.persistence.migrations.model import (
    APPLICATION_ID,
    Migration,
    migration_checksum,
)
from document_intake.persistence.migrations.v0001_initial import MIGRATION as V0001_INITIAL
from document_intake.persistence.migrations.v0002_stored_artifacts import (
    MIGRATION as V0002_STORED_ARTIFACTS,
)
from document_intake.persistence.migrations.v0003_audit_events import (
    MIGRATION as V0003_AUDIT_EVENTS,
)
from document_intake.persistence.migrations.v0004_source_file_import import MIGRATION as V0004_SOURCE_FILE_IMPORT

MIGRATIONS: tuple[Migration, ...] = (V0001_INITIAL, V0002_STORED_ARTIFACTS, V0003_AUDIT_EVENTS, V0004_SOURCE_FILE_IMPORT)
CURRENT_SCHEMA_VERSION = 4

__all__ = [
    "APPLICATION_ID",
    "CURRENT_SCHEMA_VERSION",
    "MIGRATIONS",
    "Migration",
    "migration_checksum",
]
