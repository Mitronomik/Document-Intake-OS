"""Application snapshot policy."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from document_intake.domain.entities import Application, ApplicationSnapshot
from document_intake.domain.enums import ApplicationStatus, TerminalCode
from document_intake.domain.errors import SnapshotInvariantError
from document_intake.domain.policies.verification import (
    CRITICAL_FIELD_KEYS,
    unresolved_required_fields,
)
from document_intake.domain.value_objects import (
    ActorRef,
    EntityId,
    FieldRef,
    NonEmptyText,
    SnapshotPayload,
)


def _require_aware(value: datetime, invariant: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SnapshotInvariantError(f"{invariant}: timezone_aware_required")


def _utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def calculate_snapshot_sha256(
    *,
    application_id: EntityId,
    terminal_code: TerminalCode,
    template_version: NonEmptyText,
    rules_version: NonEmptyText,
    created_by: ActorRef,
    created_at: datetime,
    payload: SnapshotPayload,
    document_artifact_refs: tuple[EntityId, ...],
) -> str:
    semantic = {
        "application_id": str(application_id),
        "terminal_code": terminal_code.value,
        "template_version": template_version.value,
        "rules_version": rules_version.value,
        "created_by": {"actor_id": str(created_by.actor_id), "actor_kind": created_by.kind.value},
        "created_at": _utc_iso(created_at),
        "payload": payload.as_dict(),
        "document_artifact_refs": [str(ref) for ref in document_artifact_refs],
    }
    canonical = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_application_snapshot(
    application: Application,
    *,
    snapshot_id: EntityId,
    payload: SnapshotPayload,
    document_artifact_refs: tuple[EntityId, ...],
    template_version: NonEmptyText,
    rules_version: NonEmptyText,
    created_by: ActorRef,
    created_at: datetime,
    required_critical_fields: frozenset[FieldRef],
) -> ApplicationSnapshot:
    _require_aware(created_at, "create_application_snapshot.created_at")
    if application.status != ApplicationStatus.READY_FOR_SNAPSHOT:
        raise SnapshotInvariantError(f"application.status: {application.status}")
    if application.terminal_code is None:
        raise SnapshotInvariantError("application.terminal_code: required")
    if application.validation_report.has_blocking_issues:
        raise SnapshotInvariantError("application.validation_report: blocking_issues")
    non_critical = [
        ref for ref in required_critical_fields if ref.field_key not in CRITICAL_FIELD_KEYS
    ]
    if non_critical:
        raise SnapshotInvariantError("required_critical_fields: non_critical_key")
    if len(set(document_artifact_refs)) != len(document_artifact_refs):
        raise SnapshotInvariantError("document_artifact_refs: duplicate")
    unresolved = unresolved_required_fields(application.verified_fields, required_critical_fields)
    if unresolved:
        raise SnapshotInvariantError("required_critical_fields: unresolved")

    artifact_refs = tuple(document_artifact_refs)
    sha256 = calculate_snapshot_sha256(
        application_id=application.id,
        terminal_code=application.terminal_code,
        template_version=template_version,
        rules_version=rules_version,
        created_by=created_by,
        created_at=created_at,
        payload=payload,
        document_artifact_refs=artifact_refs,
    )
    snapshot = ApplicationSnapshot(
        id=snapshot_id,
        application_id=application.id,
        terminal_code=application.terminal_code,
        template_version=template_version,
        rules_version=rules_version,
        created_by=created_by,
        created_at=created_at,
        payload=payload,
        document_artifact_refs=artifact_refs,
        sha256=sha256,
    )
    application.status = ApplicationStatus.SNAPSHOTTED
    application.updated_at = created_at
    return snapshot
