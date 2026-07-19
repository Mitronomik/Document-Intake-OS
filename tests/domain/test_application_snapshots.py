from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_intake.domain import (
    ActorKind,
    ActorRef,
    Application,
    ApplicationSnapshot,
    ApplicationStatus,
    EntityId,
    FieldKey,
    FieldRef,
    InvalidValueError,
    NonEmptyText,
    SnapshotInvariantError,
    SnapshotPayload,
    TerminalCode,
    ValidationIssue,
    ValidationReport,
    VerificationStatus,
    VerifiedField,
    admin_override,
    create_application_snapshot,
    mark_conflict,
    mark_not_applicable,
    rehydrate_application_snapshot,
    verify_by_human,
)
from document_intake.domain.policies.snapshots import (
    _SNAPSHOT_FACTORY_TOKEN,
    _calculate_snapshot_sha256,
)


def eid(i: int) -> EntityId:
    return EntityId(UUID(int=i))


def actor(kind: ActorKind = ActorKind.OPERATOR) -> ActorRef:
    return ActorRef(eid(100), kind)


def ref(i: int, key: str = "identity_document.number") -> FieldRef:
    return FieldRef(eid(i), FieldKey(key))


NOW = datetime(2026, 1, 1, tzinfo=UTC)
REQ = frozenset({ref(1)})


def verified(status: VerificationStatus = VerificationStatus.VERIFIED) -> VerifiedField:
    base = VerifiedField(ref(1), None, VerificationStatus.UNVERIFIED)
    if status == VerificationStatus.VERIFIED:
        return verify_by_human(base, value=NonEmptyText("ok"), actor=actor(), at=NOW)
    if status == VerificationStatus.NOT_APPLICABLE:
        return mark_not_applicable(ref(1), actor=actor(), at=NOW)
    return admin_override(
        base,
        value=NonEmptyText("ok"),
        actor=actor(ActorKind.ADMIN),
        at=NOW,
        reason=NonEmptyText("safe reason"),
    )


def app(**kwargs: object) -> Application:
    data = dict(
        id=eid(1),
        batch_id=eid(2),
        terminal_code=TerminalCode.TSP,
        assignments=(),
        verified_fields=(verified(),),
        validation_report=ValidationReport(),
        status=ApplicationStatus.READY_FOR_SNAPSHOT,
        created_by=actor(),
        created_at=NOW,
        updated_at=NOW,
    )
    data.update(kwargs)
    return Application(**data)  # type: ignore[arg-type]


def make_snapshot(
    application: Application,
    payload: SnapshotPayload | None = None,
    artifacts: tuple[EntityId, ...] = (eid(9),),
    required: frozenset[FieldRef] = REQ,
) -> ApplicationSnapshot:
    return create_application_snapshot(
        application,
        snapshot_id=eid(50),
        payload=payload or SnapshotPayload({"b": [1, {"a": True}]}),
        document_artifact_refs=artifacts,
        template_version=NonEmptyText("template-v1"),
        rules_version=NonEmptyText("rules-v1"),
        created_by=actor(),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        required_critical_fields=required,
    )


@pytest.mark.parametrize("bad_app", [app(terminal_code=None), app(status=ApplicationStatus.DRAFT)])
def test_snapshot_blocked_without_terminal_or_ready_status(bad_app: Application) -> None:
    old = (bad_app.status, bad_app.updated_at)
    with pytest.raises(SnapshotInvariantError):
        make_snapshot(bad_app)
    assert (bad_app.status, bad_app.updated_at) == old


def test_snapshot_blocking_validation_and_required_fields() -> None:
    issue = ValidationIssue(NonEmptyText("safe_code"), NonEmptyText("safe message"), True)
    for bad in [
        app(validation_report=ValidationReport((issue,))),
        app(
            verified_fields=(
                mark_conflict(VerifiedField(ref(1), None, VerificationStatus.UNVERIFIED)),
            )
        ),
        app(verified_fields=()),
    ]:
        old = (bad.status, bad.updated_at)
        with pytest.raises(SnapshotInvariantError):
            make_snapshot(bad)
        assert (bad.status, bad.updated_at) == old
    with pytest.raises(SnapshotInvariantError):
        make_snapshot(app(), required=frozenset({ref(2, "person.full_name_latin")}))


@pytest.mark.parametrize(
    "status",
    [
        VerificationStatus.VERIFIED,
        VerificationStatus.NOT_APPLICABLE,
        VerificationStatus.ADMIN_OVERRIDE,
    ],
)
def test_resolved_statuses_satisfy_gate(status: VerificationStatus) -> None:
    application = app(verified_fields=(verified(status),))
    snapshot = make_snapshot(application)
    assert snapshot.application_id == application.id
    assert application.status == ApplicationStatus.SNAPSHOTTED


def test_duplicate_artifacts_and_payload_validation() -> None:
    with pytest.raises(SnapshotInvariantError):
        make_snapshot(app(), artifacts=(eid(9), eid(9)))
    with pytest.raises(InvalidValueError):
        SnapshotPayload({"amount": 1.2})
    with pytest.raises(InvalidValueError):
        SnapshotPayload({1: "bad"})  # type: ignore[dict-item]


def test_payload_immutable_snapshot_frozen_hash_deterministic_and_artifact_order() -> None:
    source = {"z": [1], "a": {"b": "c"}}
    payload = SnapshotPayload(source)
    source["z"].append(2)  # type: ignore[attr-defined]
    application = app()
    snapshot = make_snapshot(application, payload=payload, artifacts=(eid(8), eid(9)))
    assert snapshot.payload.as_dict() == {"a": {"b": "c"}, "z": [1]}
    with pytest.raises(FrozenInstanceError):
        snapshot.sha256 = "bad"  # type: ignore[misc]
    payload2 = SnapshotPayload({"a": {"b": "c"}, "z": [1]})
    same = _calculate_snapshot_sha256(
        application_id=eid(1),
        terminal_code=TerminalCode.TSP,
        template_version=NonEmptyText("template-v1"),
        rules_version=NonEmptyText("rules-v1"),
        created_by=actor(),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        payload=payload2,
        document_artifact_refs=(eid(8), eid(9)),
    )
    other = _calculate_snapshot_sha256(
        application_id=eid(1),
        terminal_code=TerminalCode.TSP,
        template_version=NonEmptyText("template-v1"),
        rules_version=NonEmptyText("rules-v1"),
        created_by=actor(),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        payload=payload2,
        document_artifact_refs=(eid(9), eid(8)),
    )
    assert snapshot.sha256 == same
    assert same != other
    with pytest.raises(SnapshotInvariantError):
        ApplicationSnapshot(
            eid(99),
            eid(1),
            TerminalCode.TSP,
            NonEmptyText("template-v1"),
            NonEmptyText("rules-v1"),
            actor(),
            datetime(2026, 1, 2, tzinfo=UTC),
            payload2,
            (eid(8), eid(9)),
            "bad",
        )
    before = snapshot.sha256
    application.verified_fields = ()
    assert snapshot.sha256 == before


def test_application_status_is_read_only_and_factory_transitions() -> None:
    application = app()
    with pytest.raises(AttributeError):
        application.status = ApplicationStatus.SNAPSHOTTED  # type: ignore[misc]
    assert application.status == ApplicationStatus.READY_FOR_SNAPSHOT
    make_snapshot(application)
    assert application.status == ApplicationStatus.SNAPSHOTTED


def test_malformed_resolved_fields_cannot_bypass_snapshot_gate() -> None:
    with pytest.raises(InvalidValueError):
        VerifiedField(ref(1), None, VerificationStatus.VERIFIED, actor(), NOW)
    with pytest.raises(InvalidValueError):
        VerifiedField(ref(1), NonEmptyText("bad"), VerificationStatus.NOT_APPLICABLE, actor(), NOW)
    with pytest.raises(InvalidValueError):
        VerifiedField(
            ref(1),
            None,
            VerificationStatus.ADMIN_OVERRIDE,
            actor(ActorKind.ADMIN),
            NOW,
            override_reason=NonEmptyText("safe reason"),
        )


def test_public_api_hides_hash_helper_and_internal_hash_rejects_naive_datetime() -> None:
    import document_intake.domain as domain

    assert "calculate_snapshot_sha256" not in domain.__all__
    assert "_calculate_snapshot_sha256" not in domain.__all__
    with pytest.raises(SnapshotInvariantError):
        _calculate_snapshot_sha256(
            application_id=eid(1),
            terminal_code=TerminalCode.TSP,
            template_version=NonEmptyText("template-v1"),
            rules_version=NonEmptyText("rules-v1"),
            created_by=actor(),
            created_at=datetime(2026, 1, 2),
            payload=SnapshotPayload({"safe": "value"}),
            document_artifact_refs=(eid(8),),
        )


def test_direct_snapshot_construction_requires_factory_token_and_tamper_rejected() -> None:
    payload = SnapshotPayload({"safe": "value"})
    with pytest.raises(SnapshotInvariantError):
        ApplicationSnapshot(
            eid(99),
            eid(1),
            TerminalCode.TSP,
            NonEmptyText("template-v1"),
            NonEmptyText("rules-v1"),
            actor(),
            datetime(2026, 1, 2, tzinfo=UTC),
            payload,
            (eid(8),),
            _calculate_snapshot_sha256(
                application_id=eid(1),
                terminal_code=TerminalCode.TSP,
                template_version=NonEmptyText("template-v1"),
                rules_version=NonEmptyText("rules-v1"),
                created_by=actor(),
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
                payload=payload,
                document_artifact_refs=(eid(8),),
            ),
        )
    with pytest.raises(SnapshotInvariantError):
        ApplicationSnapshot(
            eid(99),
            eid(1),
            TerminalCode.TSP,
            NonEmptyText("template-v1"),
            NonEmptyText("rules-v1"),
            actor(),
            datetime(2026, 1, 2, tzinfo=UTC),
            payload,
            (eid(8),),
            "bad",
            _factory_token=_SNAPSHOT_FACTORY_TOKEN,
        )


def test_rehydrate_application_snapshot_verifies_hash_without_mutating_application() -> None:
    application = app()
    snapshot = make_snapshot(application)
    before = (application.status, application.updated_at)
    restored = rehydrate_application_snapshot(
        snapshot_id=snapshot.id,
        application_id=snapshot.application_id,
        terminal_code=snapshot.terminal_code,
        template_version=snapshot.template_version,
        rules_version=snapshot.rules_version,
        created_by=snapshot.created_by,
        created_at=snapshot.created_at,
        payload=snapshot.payload,
        document_artifact_refs=snapshot.document_artifact_refs,
        sha256=snapshot.sha256,
    )
    assert restored == snapshot
    assert (application.status, application.updated_at) == before
    with pytest.raises(SnapshotInvariantError):
        rehydrate_application_snapshot(
            snapshot_id=snapshot.id,
            application_id=snapshot.application_id,
            terminal_code=snapshot.terminal_code,
            template_version=snapshot.template_version,
            rules_version=snapshot.rules_version,
            created_by=snapshot.created_by,
            created_at=snapshot.created_at,
            payload=snapshot.payload,
            document_artifact_refs=snapshot.document_artifact_refs,
            sha256="0" * 64,
        )
