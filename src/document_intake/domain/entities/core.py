"""Core domain entities."""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from datetime import date, datetime

from document_intake.domain.enums import (
    ActorKind,
    ApplicationStatus,
    CandidateSourceType,
    DocumentType,
    DocumentWorkflowStatus,
    TerminalCode,
    VehicleRole,
    VerificationStatus,
)
from document_intake.domain.errors import InvalidValueError, SnapshotInvariantError
from document_intake.domain.value_objects import (
    ActorRef,
    Confidence,
    CountryCode,
    EntityId,
    FieldRef,
    IdentifierText,
    NonEmptyText,
    OwnerRef,
    SnapshotPayload,
    ValidationReport,
)


def _require_aware(value: datetime, invariant: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidValueError(f"{invariant}: timezone_aware_required")


@dataclass(slots=True)
class Person:
    id: EntityId
    full_name_cyrillic: NonEmptyText | None = None
    full_name_latin: NonEmptyText | None = None
    birth_date: date | None = None
    birth_place: NonEmptyText | None = None
    sex: NonEmptyText | None = None
    citizenship: CountryCode | None = None
    phone: IdentifierText | None = None
    registration_address: NonEmptyText | None = None

    def __repr__(self) -> str:
        return f"Person(id={self.id})"


@dataclass(slots=True)
class IdentityDocument:
    id: EntityId
    person_id: EntityId
    document_type: DocumentType
    series: IdentifierText | None = None
    number: IdentifierText | None = None
    full_number: IdentifierText | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    issuer: NonEmptyText | None = None
    division_code: IdentifierText | None = None
    personal_number: IdentifierText | None = None
    mrz_raw: NonEmptyText | None = None
    mrz_validation_status: NonEmptyText | None = None

    def __repr__(self) -> str:
        return (
            f"IdentityDocument(id={self.id}, person_id={self.person_id}, type={self.document_type})"
        )


@dataclass(slots=True)
class MigrationDocument:
    id: EntityId
    person_id: EntityId
    series: IdentifierText | None = None
    number: IdentifierText | None = None
    arrival_date: date | None = None
    end_date: date | None = None
    declared_identity_number: IdentifierText | None = None
    declared_citizenship: CountryCode | None = None
    stamp_data: NonEmptyText | None = None
    related_passport_id: EntityId | None = None

    def __repr__(self) -> str:
        return f"MigrationDocument(id={self.id}, person_id={self.person_id})"


@dataclass(slots=True)
class Vehicle:
    id: EntityId
    role: VehicleRole
    registration_number: IdentifierText | None = None
    vin: IdentifierText | None = None
    chassis_number: IdentifierText | None = None
    body_number: IdentifierText | None = None
    make: NonEmptyText | None = None
    model: NonEmptyText | None = None
    year: int | None = None
    color: NonEmptyText | None = None
    vehicle_type: NonEmptyText | None = None
    max_mass: int | None = None
    unladen_mass: int | None = None
    owner: OwnerRef | None = None
    registration_document_id: EntityId | None = None

    def __repr__(self) -> str:
        return f"Vehicle(id={self.id}, role={self.role})"


@dataclass(slots=True)
class Terminal:
    code: TerminalCode
    display_name: NonEmptyText
    adapter_version: NonEmptyText | None = None
    template_version: NonEmptyText | None = None
    template_checksum: NonEmptyText | None = None
    rules_version: NonEmptyText | None = None
    is_active: bool = True


@dataclass(slots=True, init=False)
class Document:
    id: EntityId
    document_type: DocumentType
    _workflow_status: DocumentWorkflowStatus
    country_code: CountryCode | None = None
    template_version: NonEmptyText | None = None
    owner_ref: OwnerRef | None = None
    side_ids: tuple[EntityId, ...] = ()
    prepared_artifact_id: EntityId | None = None

    def __init__(
        self,
        id: EntityId,
        document_type: DocumentType,
        workflow_status: DocumentWorkflowStatus,
        country_code: CountryCode | None = None,
        template_version: NonEmptyText | None = None,
        owner_ref: OwnerRef | None = None,
        side_ids: tuple[EntityId, ...] = (),
        prepared_artifact_id: EntityId | None = None,
    ) -> None:
        self.id = id
        self.document_type = document_type
        self._workflow_status = workflow_status
        self.country_code = country_code
        self.template_version = template_version
        self.owner_ref = owner_ref
        self.side_ids = tuple(side_ids)
        self.prepared_artifact_id = prepared_artifact_id
        if len(set(self.side_ids)) != len(self.side_ids):
            raise InvalidValueError("document.side_ids: duplicate")

    @property
    def workflow_status(self) -> DocumentWorkflowStatus:
        return self._workflow_status

    def _transition_workflow_status(self, target: DocumentWorkflowStatus) -> None:
        self._workflow_status = target

    def __repr__(self) -> str:
        return (
            f"Document(id={self.id}, type={self.document_type}, "
            f"status={self.workflow_status}, side_count={len(self.side_ids)})"
        )


@dataclass(frozen=True, slots=True)
class FieldCandidate:
    id: EntityId
    field_ref: FieldRef
    raw_value: NonEmptyText
    normalized_value: NonEmptyText | None
    source_type: CandidateSourceType
    confidence: Confidence
    source_region: NonEmptyText | None = None
    validation_results: tuple[NonEmptyText, ...] = ()
    conflict_group: NonEmptyText | None = None
    recognition_run_id: EntityId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "validation_results", tuple(self.validation_results))

    def __repr__(self) -> str:
        return (
            f"FieldCandidate(id={self.id}, field_ref={self.field_ref}, "
            f"source_type={self.source_type}, confidence={self.confidence.value})"
        )


@dataclass(frozen=True, slots=True)
class VerifiedField:
    field_ref: FieldRef
    value: NonEmptyText | None
    status: VerificationStatus
    actor: ActorRef | None = None
    timestamp: datetime | None = None
    source_candidate_id: EntityId | None = None
    override_reason: NonEmptyText | None = None

    def __post_init__(self) -> None:
        if self.status == VerificationStatus.VERIFIED:
            if self.value is None:
                raise InvalidValueError("verified_field.VERIFIED: value_required")
            if self.actor is None or self.timestamp is None:
                raise InvalidValueError("verified_field.VERIFIED: actor_timestamp_required")
            if self.actor.kind not in {ActorKind.OPERATOR, ActorKind.ADMIN}:
                raise InvalidValueError("verified_field.VERIFIED: human_actor_required")
            _require_aware(self.timestamp, "verified_field.VERIFIED")
        if self.status == VerificationStatus.NOT_APPLICABLE:
            if self.value is not None:
                raise InvalidValueError("verified_field.NOT_APPLICABLE: value_forbidden")
            if self.actor is None or self.timestamp is None:
                raise InvalidValueError("verified_field.NOT_APPLICABLE: actor_timestamp_required")
            if self.actor.kind not in {ActorKind.OPERATOR, ActorKind.ADMIN}:
                raise InvalidValueError("verified_field.NOT_APPLICABLE: human_actor_required")
            _require_aware(self.timestamp, "verified_field.NOT_APPLICABLE")
        if self.status == VerificationStatus.ADMIN_OVERRIDE:
            if self.value is None:
                raise InvalidValueError("verified_field.ADMIN_OVERRIDE: value_required")
            if self.actor is None or self.actor.kind != ActorKind.ADMIN or self.timestamp is None:
                raise InvalidValueError(
                    "verified_field.ADMIN_OVERRIDE: admin_actor_timestamp_required"
                )
            _require_aware(self.timestamp, "verified_field.ADMIN_OVERRIDE")
            if self.override_reason is None:
                raise InvalidValueError("verified_field.ADMIN_OVERRIDE: reason_required")
        if self.status == VerificationStatus.UNVERIFIED and self.timestamp is not None:
            raise InvalidValueError("verified_field.UNVERIFIED: timestamp_forbidden")

    def __repr__(self) -> str:
        return f"VerifiedField(field_ref={self.field_ref}, status={self.status})"


@dataclass(frozen=True, slots=True)
class ParticipantAssignment:
    person_id: EntityId
    tractor_id: EntityId
    trailer_id: EntityId | None = None
    pass_type: NonEmptyText | None = None
    position: NonEmptyText | None = None
    organization: NonEmptyText | None = None

    def __post_init__(self) -> None:
        if self.trailer_id is not None and self.tractor_id == self.trailer_id:
            raise InvalidValueError("participant_assignment: tractor_trailer_same")

    def __repr__(self) -> str:
        return (
            f"ParticipantAssignment(person_id={self.person_id}, tractor_id={self.tractor_id}, "
            f"has_trailer={self.trailer_id is not None})"
        )


@dataclass(slots=True, init=False)
class Application:
    id: EntityId
    batch_id: EntityId
    terminal_code: TerminalCode | None
    assignments: tuple[ParticipantAssignment, ...]
    verified_fields: tuple[VerifiedField, ...]
    validation_report: ValidationReport
    _status: ApplicationStatus
    created_by: ActorRef
    created_at: datetime
    updated_at: datetime

    def __init__(
        self,
        id: EntityId,
        batch_id: EntityId,
        terminal_code: TerminalCode | None,
        assignments: tuple[ParticipantAssignment, ...],
        verified_fields: tuple[VerifiedField, ...],
        validation_report: ValidationReport,
        status: ApplicationStatus,
        created_by: ActorRef,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        _require_aware(created_at, "application.created_at")
        _require_aware(updated_at, "application.updated_at")
        self.id = id
        self.batch_id = batch_id
        self.terminal_code = terminal_code
        self.assignments = tuple(assignments)
        self.verified_fields = tuple(verified_fields)
        self.validation_report = validation_report
        self._status = status
        self.created_by = created_by
        self.created_at = created_at
        self.updated_at = updated_at
        refs = [field.field_ref for field in self.verified_fields]
        if len(set(refs)) != len(refs):
            raise InvalidValueError("application.verified_fields: duplicate_field_ref")

    @property
    def status(self) -> ApplicationStatus:
        return self._status

    def _mark_snapshotted(self, *, at: datetime) -> None:
        _require_aware(at, "application.snapshotted_at")
        if self._status != ApplicationStatus.READY_FOR_SNAPSHOT:
            raise InvalidValueError("application.snapshot_transition: invalid_source")
        self._status = ApplicationStatus.SNAPSHOTTED
        self.updated_at = at

    def __repr__(self) -> str:
        return (
            f"Application(id={self.id}, status={self.status}, terminal_code={self.terminal_code}, "
            f"assignment_count={len(self.assignments)}, "
            f"verified_field_count={len(self.verified_fields)})"
        )


@dataclass(frozen=True, slots=True)
class ApplicationSnapshot:
    id: EntityId
    application_id: EntityId
    terminal_code: TerminalCode
    template_version: NonEmptyText
    rules_version: NonEmptyText
    created_by: ActorRef
    created_at: datetime
    payload: SnapshotPayload
    document_artifact_refs: tuple[EntityId, ...]
    sha256: str
    _factory_token: InitVar[object | None] = None

    def __post_init__(self, _factory_token: object | None) -> None:
        from document_intake.domain.policies.snapshots import _SNAPSHOT_FACTORY_TOKEN

        if _factory_token is not _SNAPSHOT_FACTORY_TOKEN:
            raise SnapshotInvariantError("application_snapshot.factory_required")
        _require_aware(self.created_at, "application_snapshot.created_at")
        object.__setattr__(self, "document_artifact_refs", tuple(self.document_artifact_refs))
        if len(set(self.document_artifact_refs)) != len(self.document_artifact_refs):
            raise SnapshotInvariantError("application_snapshot.artifact_refs: duplicate")
        from document_intake.domain.policies.snapshots import _calculate_snapshot_sha256

        expected = _calculate_snapshot_sha256(
            application_id=self.application_id,
            terminal_code=self.terminal_code,
            template_version=self.template_version,
            rules_version=self.rules_version,
            created_by=self.created_by,
            created_at=self.created_at,
            payload=self.payload,
            document_artifact_refs=self.document_artifact_refs,
        )
        if self.sha256 != expected:
            raise SnapshotInvariantError("application_snapshot.sha256: mismatch")

    def __repr__(self) -> str:
        return (
            f"ApplicationSnapshot(id={self.id}, application_id={self.application_id}, "
            f"terminal_code={self.terminal_code}, "
            f"artifact_count={len(self.document_artifact_refs)})"
        )
