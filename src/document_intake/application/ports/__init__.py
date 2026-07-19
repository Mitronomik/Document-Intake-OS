"""Application port contracts."""

from document_intake.application.ports.persistence import (
    ApplicationRepository,
    ApplicationSnapshotRepository,
    DatabaseKeyProvider,
    DocumentRepository,
    FieldCandidateRepository,
    IdentityDocumentRepository,
    MigrationDocumentRepository,
    PersonRepository,
    TerminalRepository,
    UnitOfWork,
    VehicleRepository,
)

__all__ = [
    "ApplicationRepository",
    "ApplicationSnapshotRepository",
    "DatabaseKeyProvider",
    "DocumentRepository",
    "FieldCandidateRepository",
    "IdentityDocumentRepository",
    "MigrationDocumentRepository",
    "PersonRepository",
    "TerminalRepository",
    "UnitOfWork",
    "VehicleRepository",
]
