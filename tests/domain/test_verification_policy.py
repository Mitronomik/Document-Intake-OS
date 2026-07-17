from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_intake.domain import (
    ActorKind,
    ActorRef,
    CandidateSourceType,
    Confidence,
    EntityId,
    FieldCandidate,
    FieldKey,
    FieldRef,
    InvalidValueError,
    NonEmptyText,
    VerificationPolicyError,
    VerificationStatus,
    VerifiedField,
    admin_override,
    draft_from_candidate,
    mark_conflict,
    mark_not_applicable,
    unresolved_required_fields,
    verify_by_human,
)


def eid(i: int) -> EntityId:
    return EntityId(UUID(int=i))


def actor(kind: ActorKind) -> ActorRef:
    return ActorRef(eid(100 + len(kind.value)), kind)


def ref(i: int, key: str = "identity_document.number") -> FieldRef:
    return FieldRef(eid(i), FieldKey(key))


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def candidate(confidence: str = "0.99") -> FieldCandidate:
    return FieldCandidate(
        eid(1),
        ref(1),
        NonEmptyText("raw-fictional"),
        NonEmptyText("norm-fictional"),
        CandidateSourceType.MRZ,
        Confidence(confidence),
    )


def test_candidate_source_confidence_and_draft_unverified() -> None:
    cand = candidate("1")
    draft = draft_from_candidate(cand)
    assert cand.source_type == CandidateSourceType.MRZ
    assert cand.confidence.value == Confidence("1").value
    assert draft.status == VerificationStatus.UNVERIFIED
    assert draft.status != VerificationStatus.VERIFIED


def test_human_verification_roles_and_admin_override() -> None:
    draft = draft_from_candidate(candidate())
    assert (
        verify_by_human(
            draft, value=NonEmptyText("ok"), actor=actor(ActorKind.OPERATOR), at=NOW
        ).status
        == VerificationStatus.VERIFIED
    )
    assert (
        verify_by_human(
            draft, value=NonEmptyText("ok"), actor=actor(ActorKind.ADMIN), at=NOW
        ).status
        == VerificationStatus.VERIFIED
    )
    with pytest.raises(VerificationPolicyError):
        verify_by_human(draft, value=NonEmptyText("ok"), actor=actor(ActorKind.SYSTEM), at=NOW)
    with pytest.raises(VerificationPolicyError):
        admin_override(
            draft,
            value=NonEmptyText("ok"),
            actor=actor(ActorKind.OPERATOR),
            at=NOW,
            reason=NonEmptyText("safe reason"),
        )
    with pytest.raises(InvalidValueError):
        NonEmptyText("")
    assert (
        admin_override(
            draft,
            value=NonEmptyText("ok"),
            actor=actor(ActorKind.ADMIN),
            at=NOW,
            reason=NonEmptyText("safe reason"),
        ).status
        == VerificationStatus.ADMIN_OVERRIDE
    )


def test_not_applicable_conflict_and_unresolved_deterministic() -> None:
    r1, r2 = ref(2), ref(1)
    assert (
        mark_not_applicable(r1, actor=actor(ActorKind.OPERATOR), at=NOW).status
        == VerificationStatus.NOT_APPLICABLE
    )
    with pytest.raises(VerificationPolicyError):
        mark_not_applicable(r1, actor=actor(ActorKind.SYSTEM), at=NOW)
    conflict = mark_conflict(VerifiedField(r1, None, VerificationStatus.UNVERIFIED))
    assert conflict.status == VerificationStatus.CONFLICT
    assert unresolved_required_fields((conflict,), frozenset({r1, r2})) == (r2, r1)


def test_same_field_key_different_entities_and_safe_reprs_errors() -> None:
    r1, r2 = ref(1), ref(2)
    f1 = verify_by_human(
        VerifiedField(r1, None, VerificationStatus.UNVERIFIED),
        value=NonEmptyText("value-one"),
        actor=actor(ActorKind.OPERATOR),
        at=NOW,
    )
    assert unresolved_required_fields((f1,), frozenset({r1, r2})) == (r2,)
    cand = candidate()
    assert "raw-fictional" not in repr(cand)
    overridden = admin_override(
        draft_from_candidate(cand),
        value=NonEmptyText("value-two"),
        actor=actor(ActorKind.ADMIN),
        at=NOW,
        reason=NonEmptyText("operator-approved reason"),
    )
    assert "value-two" not in repr(overridden)
    assert "operator-approved reason" not in repr(overridden)
    with pytest.raises(VerificationPolicyError) as exc:
        verify_by_human(
            VerifiedField(r1, None, VerificationStatus.UNVERIFIED),
            value=NonEmptyText("sensitive-value"),
            actor=actor(ActorKind.SYSTEM),
            at=NOW,
        )
    assert "sensitive-value" not in str(exc.value)


def test_direct_verified_field_invariants_prevent_bypass() -> None:
    r = ref(10)
    with pytest.raises(InvalidValueError):
        VerifiedField(
            r, NonEmptyText("ok"), VerificationStatus.VERIFIED, actor(ActorKind.SYSTEM), NOW
        )
    with pytest.raises(InvalidValueError):
        VerifiedField(r, None, VerificationStatus.VERIFIED, actor(ActorKind.OPERATOR), NOW)
    with pytest.raises(InvalidValueError):
        VerifiedField(r, None, VerificationStatus.NOT_APPLICABLE, actor(ActorKind.SYSTEM), NOW)
    with pytest.raises(InvalidValueError):
        VerifiedField(
            r,
            NonEmptyText("not allowed"),
            VerificationStatus.NOT_APPLICABLE,
            actor(ActorKind.OPERATOR),
            NOW,
        )
    with pytest.raises(InvalidValueError):
        VerifiedField(
            r,
            None,
            VerificationStatus.ADMIN_OVERRIDE,
            actor(ActorKind.ADMIN),
            NOW,
            override_reason=NonEmptyText("safe reason"),
        )
