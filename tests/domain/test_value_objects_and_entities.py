from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from document_intake.domain import (
    ActorKind,
    ActorRef,
    Application,
    ApplicationStatus,
    CandidateSourceType,
    Confidence,
    CountryCode,
    Document,
    DocumentType,
    DocumentWorkflowStatus,
    EntityId,
    FieldCandidate,
    FieldKey,
    FieldRef,
    IdentifierText,
    IdentityDocument,
    InvalidValueError,
    NonEmptyText,
    ParticipantAssignment,
    Person,
    SnapshotPayload,
    Terminal,
    TerminalCode,
    ValidationReport,
    Vehicle,
    VehicleRole,
    VerificationStatus,
    VerifiedField,
)


def eid(i: int) -> EntityId:
    return EntityId(UUID(int=i))


def actor(kind: ActorKind = ActorKind.OPERATOR) -> ActorRef:
    return ActorRef(eid(100), kind)


def field_ref(i: int, key: str = "identity_document.number") -> FieldRef:
    return FieldRef(eid(i), FieldKey(key))


def test_identifier_preserves_zeroes_and_rejects_blank_padding() -> None:
    assert IdentifierText("001234").value == "001234"
    for value in ("", "   ", " 001234", "001234 "):
        with pytest.raises(InvalidValueError):
            IdentifierText(value)


def test_country_code_and_confidence_bounds() -> None:
    assert CountryCode("BY").value == "BY"
    assert CountryCode("KAZ").value == "KAZ"
    for value in ("by", "B1", " B", "BBBB"):
        with pytest.raises(InvalidValueError):
            CountryCode(value)
    assert Confidence(0).value == Decimal("0")
    assert Confidence(1).value == Decimal("1")
    assert Confidence(0.1).value == Decimal("0.1")
    for value in ("NaN", "Infinity", "-0.1", "1.1"):
        with pytest.raises(InvalidValueError):
            Confidence(value)


def test_timestamp_invariants_reject_naive() -> None:
    with pytest.raises(InvalidValueError):
        VerifiedField(
            field_ref(1),
            NonEmptyText("fictional"),
            VerificationStatus.VERIFIED,
            actor(),
            datetime(2026, 1, 1),
        )
    with pytest.raises(InvalidValueError):
        Application(
            eid(1),
            eid(2),
            TerminalCode.TSP,
            (),
            (),
            ValidationReport(),
            ApplicationStatus.DRAFT,
            actor(),
            datetime(2026, 1, 1),
            datetime.now(UTC),
        )


def test_entity_invariants_and_boundaries() -> None:
    with pytest.raises(InvalidValueError):
        Document(
            eid(1), DocumentType.PASSPORT, DocumentWorkflowStatus.NEW, side_ids=(eid(2), eid(2))
        )
    with pytest.raises(InvalidValueError):
        ParticipantAssignment(eid(1), eid(2), eid(2))
    vehicle = Vehicle(eid(3), VehicleRole.TRACTOR, vin=IdentifierText("VINFICTIONAL001"))
    assert not hasattr(vehicle, "person_id")
    terminal = Terminal(TerminalCode.VISITORS, NonEmptyText("Internal Visitors Template"))
    assert terminal.code != terminal.display_name


def test_duplicate_application_field_refs_fail() -> None:
    vf = VerifiedField(field_ref(1), None, VerificationStatus.UNVERIFIED)
    with pytest.raises(InvalidValueError):
        Application(
            eid(1),
            eid(2),
            None,
            (),
            (vf, vf),
            ValidationReport(),
            ApplicationStatus.DRAFT,
            actor(),
            datetime.now(UTC),
            datetime.now(UTC),
        )


def test_safe_reprs_exclude_values() -> None:
    secretish = ["Fictional Name", "001234", "5550000", "VINFICTIONAL001", "field value"]
    objects = [
        Person(eid(1), full_name_latin=NonEmptyText("Fictional Name")),
        IdentityDocument(eid(2), eid(1), DocumentType.PASSPORT, number=IdentifierText("001234")),
        Vehicle(eid(3), VehicleRole.TRACTOR, vin=IdentifierText("VINFICTIONAL001")),
        FieldCandidate(
            eid(4),
            field_ref(1),
            NonEmptyText("field value"),
            NonEmptyText("field value"),
            CandidateSourceType.VISUAL_OCR,
            Confidence("0.9"),
        ),
        VerifiedField(
            field_ref(1),
            NonEmptyText("field value"),
            VerificationStatus.VERIFIED,
            actor(),
            datetime.now(UTC),
        ),
    ]
    for obj in objects:
        text = repr(obj)
        assert all(value not in text for value in secretish)


def test_runtime_value_object_type_validation_and_safe_errors() -> None:
    with pytest.raises(InvalidValueError):
        EntityId("not-a-uuid")  # type: ignore[arg-type]
    with pytest.raises(InvalidValueError) as exc:
        EntityId.parse("not-a-uuid-sensitive")
    assert "not-a-uuid-sensitive" not in str(exc.value)
    for cls in (NonEmptyText, IdentifierText, CountryCode, FieldKey):
        with pytest.raises(InvalidValueError):
            cls(123)  # type: ignore[arg-type]
    with pytest.raises(InvalidValueError):
        Confidence(True)
    with pytest.raises(InvalidValueError):
        Confidence(object())  # type: ignore[arg-type]


def test_value_object_and_assignment_reprs_are_safe() -> None:
    text = NonEmptyText("Sensitive Fictional Text")
    identifier = IdentifierText("SECRET001")
    assert str(text) == "Sensitive Fictional Text"
    assert str(identifier) == "SECRET001"
    assert "Sensitive Fictional Text" not in repr(text)
    assert "SECRET001" not in repr(identifier)
    assignment = ParticipantAssignment(
        eid(1),
        eid(2),
        eid(3),
        pass_type=NonEmptyText("Sensitive Pass"),
        position=NonEmptyText("Sensitive Position"),
        organization=NonEmptyText("Sensitive Org"),
    )
    assignment_repr = repr(assignment)
    assert str(eid(1)) in assignment_repr
    assert str(eid(2)) in assignment_repr
    assert "has_trailer=True" in assignment_repr
    assert "Sensitive Pass" not in assignment_repr
    assert "Sensitive Position" not in assignment_repr
    assert "Sensitive Org" not in assignment_repr


def test_snapshot_payload_errors_exclude_caller_keys_and_values() -> None:
    sensitive_key = "sensitive.passport.number"
    sensitive_value = "SECRET-VALUE-001"
    with pytest.raises(InvalidValueError) as exc:
        SnapshotPayload({sensitive_key: [sensitive_value, 1.2]})
    message = str(exc.value)
    assert message == "snapshot_payload: float_forbidden"
    assert sensitive_key not in message
    assert sensitive_value not in message
    with pytest.raises(InvalidValueError) as unsupported:
        SnapshotPayload({"safe": object()})
    assert str(unsupported.value) == "snapshot_payload: unsupported_type"
