from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.storage import StorageKey
from document_intake.domain.enums import ArtifactKind
from document_intake.domain.value_objects import EntityId

KEY_BYTES = b"K" * 32
OTHER_KEY_BYTES = b"Z" * 32


class StaticKeyProvider:
    def __init__(self, key: bytes = KEY_BYTES, version: int = 1) -> None:
        self.key = key
        self.version = version

    def get_current_key(self) -> StorageKey:
        return StorageKey(self.version, self.key)

    def get_key(self, version: int) -> StorageKey:
        return StorageKey(version, self.key)


class WrongVersionProvider(StaticKeyProvider):
    def get_key(self, version: int) -> StorageKey:
        return StorageKey(version + 1, self.key)


def entity_id() -> EntityId:
    return EntityId(uuid4())


def aware_now() -> datetime:
    return datetime.now(UTC)


def publish_sample(root: Path, plaintext: bytes = b"synthetic bytes") -> StoredArtifactRecord:
    from document_intake.storage.filesystem import ImmutableFilesystemStorage

    storage = ImmutableFilesystemStorage(root, StaticKeyProvider())
    return storage.publish_bytes(
        artifact_id=entity_id(),
        artifact_kind=ArtifactKind.ORIGINAL,
        plaintext=plaintext,
        created_at=aware_now(),
    )


def with_ciphertext(record: StoredArtifactRecord, digest: str) -> StoredArtifactRecord:
    return replace(record, ciphertext_sha256=digest)
