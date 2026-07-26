"""Small deterministic, synthetic-only scaffolding for future PR-011 evidence tests."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from document_intake.domain.enums import ActorKind, ColorSpace, PreparedMediaType
from document_intake.domain.prepared_jpeg import (
    PREPARED_JPEG_OUTPUT_CONTRACT_ID,
    PREPARED_JPEG_PIPELINE_ID,
    PreparedImageArtifact,
)
from document_intake.domain.value_objects import ActorRef, EntityId, Sha256Digest
from document_intake.persistence import database
from document_intake.persistence.migrations import MIGRATIONS

STAMP = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)


def entity_id(number: int) -> EntityId:
    return EntityId(UUID(int=number))


def actor() -> ActorRef:
    return ActorRef(entity_id(90), ActorKind.SYSTEM)


def correlation_id() -> EntityId:
    return entity_id(91)


def prepared_artifact() -> PreparedImageArtifact:
    return PreparedImageArtifact(
        entity_id(40),
        entity_id(20),
        entity_id(30),
        entity_id(41),
        PREPARED_JPEG_PIPELINE_ID,
        1,
        PREPARED_JPEG_OUTPUT_CONTRACT_ID,
        1,
        PreparedMediaType.JPEG,
        ColorSpace.SRGB,
        8,
        8,
        64,
        Sha256Digest("a" * 64),
        95,
        100,
        STAMP,
        actor(),
    )


def synthetic_row(kind: str, number: int) -> dict[str, object]:
    """Return explicit non-production placeholder input for a later domain builder."""
    return {"kind": kind, "id": entity_id(number), "created_at": STAMP}


def valid_upload_batch() -> dict[str, object]:
    return synthetic_row("upload_batch", 10)


def valid_original_stored_artifact() -> dict[str, object]:
    return synthetic_row("original_stored_artifact", 11)


def valid_source_file() -> dict[str, object]:
    return synthetic_row("source_file", 20)


def valid_upload_source_association() -> dict[str, object]:
    return synthetic_row("upload_source_association", 21)


def valid_historical_audit_event() -> dict[str, object]:
    return synthetic_row("historical_audit_event", 22)


def valid_quality_audit_event() -> dict[str, object]:
    return synthetic_row("quality_audit_event", 23)


def valid_quality_assessment() -> dict[str, object]:
    return synthetic_row("quality_assessment", 24)


def valid_quality_metrics() -> dict[str, object]:
    return synthetic_row("quality_metrics", 25)


def valid_quality_issue() -> dict[str, object]:
    return synthetic_row("quality_issue", 26)


def valid_geometry_audit_event() -> dict[str, object]:
    return synthetic_row("geometry_audit_event", 27)


def valid_geometry_recipe() -> dict[str, object]:
    return synthetic_row("geometry_recipe", 30)


def valid_prepared_stored_artifact() -> dict[str, object]:
    return synthetic_row("prepared_stored_artifact", 41)


@dataclass(frozen=True, slots=True)
class V6Snapshot:
    rows_by_table: dict[str, tuple[tuple[object, ...], ...]]


def open_sqlite(path: Path, provider: object | None = None) -> sqlite3.Connection:
    del provider
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def assert_foreign_keys(connection: sqlite3.Connection) -> None:
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)


def build_schema_v6(connection: sqlite3.Connection) -> V6Snapshot:
    connection.execute("PRAGMA foreign_keys=ON")
    for migration in MIGRATIONS[:6]:
        database._apply_one_migration(connection, migration)
    tables = ("schema_migrations",)
    return V6Snapshot(
        {table: tuple(connection.execute(f"SELECT * FROM {table}").fetchall()) for table in tables}
    )


class CommitFailureUow:
    def __init__(self, delegated: Any) -> None:
        self.delegated = delegated

    def commit(self) -> None:
        raise RuntimeError("SYNTHETIC_COMMIT_FAILURE")

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegated, name)


@dataclass(slots=True)
class CallRecorder:
    calls: list[str]

    def record(self, value: str) -> None:
        self.calls.append(value)
