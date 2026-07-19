"""Application storage ports."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from document_intake.application.dto.storage import StoredArtifactRecord, StorageReconciliationReport
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId

@dataclass(frozen=True, slots=True)
class StorageKey:
    version: int
    key_bytes: bytes
    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version <= 0:
            raise ValueError("ERR_STORAGE_KEY_VERSION_INVALID")
        if not isinstance(self.key_bytes, bytes) or len(self.key_bytes) != 32:
            raise ValueError("ERR_STORAGE_KEY_INVALID")
    def __repr__(self) -> str:
        return f"StorageKey(version={self.version}, key_bytes=<redacted>)"

class StorageKeyProvider(Protocol):
    def get_current_key(self) -> StorageKey: ...
    def get_key(self, version: int) -> StorageKey: ...

class StoragePort(Protocol):
    def publish_bytes(self, *, artifact_id: EntityId, artifact_kind: ArtifactKind, plaintext: bytes, created_at: datetime) -> StoredArtifactRecord: ...
    def read_bytes(self, *, expected: StoredArtifactRecord) -> bytes: ...
    def verify(self, *, expected: StoredArtifactRecord) -> None: ...
    def reconcile(self, *, expected: tuple[StoredArtifactRecord, ...]) -> StorageReconciliationReport: ...
    def cleanup_temporary_files(self) -> int: ...
