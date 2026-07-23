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
from document_intake.persistence.migrations.v0004_source_file_import import (
    MIGRATION as V0004_SOURCE_FILE_IMPORT,
)
from document_intake.persistence.migrations.v0005_image_quality import (
    MIGRATION as V0005_IMAGE_QUALITY,
)
from document_intake.persistence.migrations.v0006_image_geometry import (
    MIGRATION as V0006_IMAGE_GEOMETRY,
)

MIGRATIONS: tuple[Migration, ...] = (
    V0001_INITIAL,
    V0002_STORED_ARTIFACTS,
    V0003_AUDIT_EVENTS,
    V0004_SOURCE_FILE_IMPORT,
    V0005_IMAGE_QUALITY,
    V0006_IMAGE_GEOMETRY,
)
CURRENT_SCHEMA_VERSION = 6

__all__ = [
    "APPLICATION_ID",
    "CURRENT_SCHEMA_VERSION",
    "MIGRATIONS",
    "Migration",
    "migration_checksum",
]
