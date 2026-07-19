"""Storage DTOs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class StoredArtifactRecord:
    artifact_id: EntityId
    artifact_kind: ArtifactKind
    object_generation: int
    plaintext_length: int
    plaintext_sha256: str
    ciphertext_sha256: str
    key_version: int
    storage_format_version: int
    created_at: datetime

    def __post_init__(self) -> None:
        if self.object_generation != 1:
            raise ValueError("ERR_STORAGE_EXPECTED_STATE_MISMATCH")
        if not isinstance(self.plaintext_length, int) or isinstance(self.plaintext_length, bool):
            raise ValueError("ERR_STORAGE_EXPECTED_STATE_MISMATCH")
        if self.plaintext_length < 0:
            raise ValueError("ERR_STORAGE_EXPECTED_STATE_MISMATCH")
        if not _SHA256_RE.fullmatch(self.plaintext_sha256):
            raise ValueError("ERR_STORAGE_EXPECTED_STATE_MISMATCH")
        if not _SHA256_RE.fullmatch(self.ciphertext_sha256):
            raise ValueError("ERR_STORAGE_EXPECTED_STATE_MISMATCH")
        if not isinstance(self.key_version, int) or isinstance(self.key_version, bool) or self.key_version <= 0:
            raise ValueError("ERR_STORAGE_KEY_VERSION_INVALID")
        if self.storage_format_version != 1:
            raise ValueError("ERR_STORAGE_EXPECTED_STATE_MISMATCH")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("ERR_STORAGE_EXPECTED_STATE_MISMATCH")

    def __repr__(self) -> str:
        return "StoredArtifactRecord(<redacted>)"


class StorageReconciliationStatus(StrEnum):
    HEALTHY = "HEALTHY"
    MISSING = "MISSING"
    INVALID = "INVALID"
    ORPHAN = "ORPHAN"
    TEMPORARY = "TEMPORARY"


@dataclass(frozen=True, slots=True)
class StorageReconciliationItem:
    status: StorageReconciliationStatus
    artifact_id: EntityId | None
    code: str

    def __repr__(self) -> str:
        return f"StorageReconciliationItem(status={self.status.value!r}, code={self.code!r})"


@dataclass(frozen=True, slots=True)
class StorageReconciliationReport:
    healthy: tuple[StorageReconciliationItem, ...]
    missing: tuple[StorageReconciliationItem, ...]
    invalid: tuple[StorageReconciliationItem, ...]
    orphan: tuple[StorageReconciliationItem, ...]
    temporary: tuple[StorageReconciliationItem, ...]

    @property
    def counts(self) -> dict[str, int]:
        return {
            "healthy": len(self.healthy),
            "missing": len(self.missing),
            "invalid": len(self.invalid),
            "orphan": len(self.orphan),
            "temporary": len(self.temporary),
        }
