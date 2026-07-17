"""Human verification and critical-field policies."""

from __future__ import annotations

from datetime import datetime

from document_intake.domain.entities import FieldCandidate, VerifiedField
from document_intake.domain.enums import ActorKind, VerificationStatus
from document_intake.domain.errors import VerificationPolicyError
from document_intake.domain.value_objects import ActorRef, FieldKey, FieldRef, NonEmptyText

CRITICAL_FIELD_KEYS = frozenset(
    FieldKey(value)
    for value in (
        "identity_document.number",
        "person.birth_date",
        "identity_document.issue_date",
        "identity_document.expiry_date",
        "vehicle.vin",
        "vehicle.tractor.registration_number",
        "vehicle.trailer.registration_number",
    )
)

RESOLVED_STATUSES = frozenset(
    {
        VerificationStatus.VERIFIED,
        VerificationStatus.NOT_APPLICABLE,
        VerificationStatus.ADMIN_OVERRIDE,
    }
)


def _require_aware(at: datetime, invariant: str) -> None:
    if at.tzinfo is None or at.utcoffset() is None:
        raise VerificationPolicyError(f"{invariant}: timezone_aware_required")


def draft_from_candidate(candidate: FieldCandidate) -> VerifiedField:
    return VerifiedField(
        field_ref=candidate.field_ref,
        value=candidate.normalized_value,
        status=VerificationStatus.UNVERIFIED,
        source_candidate_id=candidate.id,
    )


def verify_by_human(
    field: VerifiedField, *, value: NonEmptyText, actor: ActorRef, at: datetime
) -> VerifiedField:
    if actor.kind not in {ActorKind.OPERATOR, ActorKind.ADMIN}:
        raise VerificationPolicyError(f"verify_by_human: actor_kind:{actor.kind}")
    _require_aware(at, "verify_by_human")
    return VerifiedField(
        field_ref=field.field_ref,
        value=value,
        status=VerificationStatus.VERIFIED,
        actor=actor,
        timestamp=at,
        source_candidate_id=field.source_candidate_id,
    )


def mark_conflict(
    field: VerifiedField, *, actor: ActorRef | None = None, at: datetime | None = None
) -> VerifiedField:
    if at is not None:
        _require_aware(at, "mark_conflict")
    return VerifiedField(
        field_ref=field.field_ref,
        value=None,
        status=VerificationStatus.CONFLICT,
        actor=actor,
        timestamp=at,
        source_candidate_id=field.source_candidate_id,
    )


def mark_not_applicable(field_ref: FieldRef, *, actor: ActorRef, at: datetime) -> VerifiedField:
    if actor.kind == ActorKind.SYSTEM:
        raise VerificationPolicyError(f"mark_not_applicable: actor_kind:{actor.kind}")
    _require_aware(at, "mark_not_applicable")
    return VerifiedField(field_ref, None, VerificationStatus.NOT_APPLICABLE, actor, at)


def admin_override(
    field: VerifiedField,
    *,
    value: NonEmptyText,
    actor: ActorRef,
    at: datetime,
    reason: NonEmptyText,
) -> VerifiedField:
    if actor.kind != ActorKind.ADMIN:
        raise VerificationPolicyError(f"admin_override: actor_kind:{actor.kind}")
    _require_aware(at, "admin_override")
    return VerifiedField(
        field_ref=field.field_ref,
        value=value,
        status=VerificationStatus.ADMIN_OVERRIDE,
        actor=actor,
        timestamp=at,
        source_candidate_id=field.source_candidate_id,
        override_reason=reason,
    )


def unresolved_required_fields(
    fields: tuple[VerifiedField, ...], required: frozenset[FieldRef]
) -> tuple[FieldRef, ...]:
    by_ref = {field.field_ref: field for field in fields}
    unresolved = [
        field_ref
        for field_ref in required
        if field_ref not in by_ref or by_ref[field_ref].status not in RESOLVED_STATUSES
    ]
    return tuple(sorted(unresolved, key=lambda ref: (str(ref.entity_id), str(ref.field_key))))
