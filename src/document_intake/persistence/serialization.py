# ruff: noqa: F405, F403
"""Explicit JSON mappers for PR-004 domain objects."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import wraps
from typing import Any
from uuid import UUID

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.domain import *
from document_intake.domain.enums import *
from document_intake.domain.errors import DomainError
from document_intake.domain.policies import rehydrate_application_snapshot
from document_intake.domain.value_objects import *
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


def persisted_data_boundary[**P, T](function: Callable[P, T]) -> Callable[P, T]:
    """Normalize every malformed persisted representation to one safe error."""

    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return function(*args, **kwargs)
        except PersistenceError:
            raise
        except Exception:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None

    return wrapped


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return parsed


def _id(value: EntityId | None) -> str | None:
    return None if value is None else str(value)


def _text(value: Any) -> str | None:
    return None if value is None else value.value


def _date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _enum(value: Any) -> str | None:
    return None if value is None else value.value


def _actor(value: ActorRef | None) -> dict[str, str] | None:
    return None if value is None else {"actor_id": str(value.actor_id), "kind": value.kind.value}


def _owner(value: OwnerRef | None) -> dict[str, str] | None:
    return (
        None
        if value is None
        else {"owner_kind": value.owner_kind.value, "owner_id": str(value.owner_id)}
    )


def _field_ref(value: FieldRef) -> dict[str, str]:
    return {"entity_id": str(value.entity_id), "field_key": value.field_key.value}


def dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads(payload: str) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None
    if not isinstance(data, dict):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return data


def parse_id(value: str | None) -> EntityId | None:
    if value is None:
        return None
    try:
        return EntityId(UUID(value))
    except (ValueError, TypeError, DomainError):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def req_id(value: str) -> EntityId:
    parsed = parse_id(value)
    if parsed is None:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return parsed


def parse_text(cls: type[Any], value: str | None) -> Any:
    if value is None:
        return None
    try:
        return cls(value)
    except DomainError:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def parse_enum(cls: type[Any], value: str | None) -> Any:
    if value is None:
        return None
    try:
        return cls(value)
    except ValueError:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def parse_actor(value: dict[str, str] | None) -> ActorRef | None:
    if value is None:
        return None
    return ActorRef(req_id(value["actor_id"]), parse_enum(ActorKind, value["kind"]))


def parse_owner(value: dict[str, str] | None) -> OwnerRef | None:
    if value is None:
        return None
    return OwnerRef(parse_enum(OwnerKind, value["owner_kind"]), req_id(value["owner_id"]))


def parse_field_ref(value: dict[str, str]) -> FieldRef:
    return FieldRef(req_id(value["entity_id"]), FieldKey(value["field_key"]))


def person_to_json(o: Person) -> str:
    return dumps(
        {
            "id": str(o.id),
            "full_name_cyrillic": _text(o.full_name_cyrillic),
            "full_name_latin": _text(o.full_name_latin),
            "birth_date": _date(o.birth_date),
            "birth_place": _text(o.birth_place),
            "sex": _text(o.sex),
            "citizenship": _text(o.citizenship),
            "phone": _text(o.phone),
            "registration_address": _text(o.registration_address),
        }
    )


@persisted_data_boundary
def person_from_json(payload: str) -> Person:
    d = loads(payload)
    return Person(
        req_id(d["id"]),
        parse_text(NonEmptyText, d.get("full_name_cyrillic")),
        parse_text(NonEmptyText, d.get("full_name_latin")),
        parse_date(d.get("birth_date")),
        parse_text(NonEmptyText, d.get("birth_place")),
        parse_text(NonEmptyText, d.get("sex")),
        parse_text(CountryCode, d.get("citizenship")),
        parse_text(IdentifierText, d.get("phone")),
        parse_text(NonEmptyText, d.get("registration_address")),
    )


def identity_to_json(o: IdentityDocument) -> str:
    return dumps(
        {
            "id": str(o.id),
            "person_id": str(o.person_id),
            "document_type": o.document_type.value,
            "series": _text(o.series),
            "number": _text(o.number),
            "full_number": _text(o.full_number),
            "issue_date": _date(o.issue_date),
            "expiry_date": _date(o.expiry_date),
            "issuer": _text(o.issuer),
            "division_code": _text(o.division_code),
            "personal_number": _text(o.personal_number),
            "mrz_raw": _text(o.mrz_raw),
            "mrz_validation_status": _text(o.mrz_validation_status),
        }
    )


@persisted_data_boundary
def identity_from_json(payload: str) -> IdentityDocument:
    d = loads(payload)
    return IdentityDocument(
        req_id(d["id"]),
        req_id(d["person_id"]),
        parse_enum(DocumentType, d["document_type"]),
        parse_text(IdentifierText, d.get("series")),
        parse_text(IdentifierText, d.get("number")),
        parse_text(IdentifierText, d.get("full_number")),
        parse_date(d.get("issue_date")),
        parse_date(d.get("expiry_date")),
        parse_text(NonEmptyText, d.get("issuer")),
        parse_text(IdentifierText, d.get("division_code")),
        parse_text(IdentifierText, d.get("personal_number")),
        parse_text(NonEmptyText, d.get("mrz_raw")),
        parse_text(NonEmptyText, d.get("mrz_validation_status")),
    )


def migration_to_json(o: MigrationDocument) -> str:
    return dumps(
        {
            "id": str(o.id),
            "person_id": str(o.person_id),
            "series": _text(o.series),
            "number": _text(o.number),
            "arrival_date": _date(o.arrival_date),
            "end_date": _date(o.end_date),
            "declared_identity_number": _text(o.declared_identity_number),
            "declared_citizenship": _text(o.declared_citizenship),
            "stamp_data": _text(o.stamp_data),
            "related_passport_id": _id(o.related_passport_id),
        }
    )


@persisted_data_boundary
def migration_from_json(payload: str) -> MigrationDocument:
    d = loads(payload)
    return MigrationDocument(
        req_id(d["id"]),
        req_id(d["person_id"]),
        parse_text(IdentifierText, d.get("series")),
        parse_text(IdentifierText, d.get("number")),
        parse_date(d.get("arrival_date")),
        parse_date(d.get("end_date")),
        parse_text(IdentifierText, d.get("declared_identity_number")),
        parse_text(CountryCode, d.get("declared_citizenship")),
        parse_text(NonEmptyText, d.get("stamp_data")),
        parse_id(d.get("related_passport_id")),
    )


def vehicle_to_json(o: Vehicle) -> str:
    return dumps(
        {
            "id": str(o.id),
            "role": o.role.value,
            "registration_number": _text(o.registration_number),
            "vin": _text(o.vin),
            "chassis_number": _text(o.chassis_number),
            "body_number": _text(o.body_number),
            "make": _text(o.make),
            "model": _text(o.model),
            "year": o.year,
            "color": _text(o.color),
            "vehicle_type": _text(o.vehicle_type),
            "max_mass": o.max_mass,
            "unladen_mass": o.unladen_mass,
            "owner": _owner(o.owner),
            "registration_document_id": _id(o.registration_document_id),
        }
    )


@persisted_data_boundary
def vehicle_from_json(payload: str) -> Vehicle:
    d = loads(payload)
    return Vehicle(
        req_id(d["id"]),
        parse_enum(VehicleRole, d["role"]),
        parse_text(IdentifierText, d.get("registration_number")),
        parse_text(IdentifierText, d.get("vin")),
        parse_text(IdentifierText, d.get("chassis_number")),
        parse_text(IdentifierText, d.get("body_number")),
        parse_text(NonEmptyText, d.get("make")),
        parse_text(NonEmptyText, d.get("model")),
        d.get("year"),
        parse_text(NonEmptyText, d.get("color")),
        parse_text(NonEmptyText, d.get("vehicle_type")),
        d.get("max_mass"),
        d.get("unladen_mass"),
        parse_owner(d.get("owner")),
        parse_id(d.get("registration_document_id")),
    )


def terminal_to_json(o: Terminal) -> str:
    return dumps(
        {
            "code": o.code.value,
            "display_name": _text(o.display_name),
            "adapter_version": _text(o.adapter_version),
            "template_version": _text(o.template_version),
            "template_checksum": _text(o.template_checksum),
            "rules_version": _text(o.rules_version),
            "is_active": o.is_active,
        }
    )


@persisted_data_boundary
def terminal_from_json(payload: str) -> Terminal:
    d = loads(payload)
    is_active = d["is_active"]
    if type(is_active) is not bool:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return Terminal(
        parse_enum(TerminalCode, d["code"]),
        parse_text(NonEmptyText, d["display_name"]),
        parse_text(NonEmptyText, d.get("adapter_version")),
        parse_text(NonEmptyText, d.get("template_version")),
        parse_text(NonEmptyText, d.get("template_checksum")),
        parse_text(NonEmptyText, d.get("rules_version")),
        is_active,
    )


def document_to_json(o: Document) -> str:
    return dumps(
        {
            "id": str(o.id),
            "document_type": o.document_type.value,
            "workflow_status": o.workflow_status.value,
            "country_code": _text(o.country_code),
            "template_version": _text(o.template_version),
            "owner_ref": _owner(o.owner_ref),
            "side_ids": [str(x) for x in o.side_ids],
            "prepared_artifact_id": _id(o.prepared_artifact_id),
        }
    )


@persisted_data_boundary
def document_from_json(payload: str) -> Document:
    d = loads(payload)
    return Document(
        req_id(d["id"]),
        parse_enum(DocumentType, d["document_type"]),
        parse_enum(DocumentWorkflowStatus, d["workflow_status"]),
        parse_text(CountryCode, d.get("country_code")),
        parse_text(NonEmptyText, d.get("template_version")),
        parse_owner(d.get("owner_ref")),
        tuple(req_id(x) for x in d["side_ids"]),
        parse_id(d.get("prepared_artifact_id")),
    )


def candidate_to_json(o: FieldCandidate) -> str:
    return dumps(
        {
            "id": str(o.id),
            "field_ref": _field_ref(o.field_ref),
            "raw_value": _text(o.raw_value),
            "normalized_value": _text(o.normalized_value),
            "source_type": o.source_type.value,
            "confidence": str(o.confidence.value),
            "source_region": _text(o.source_region),
            "validation_results": [x.value for x in o.validation_results],
            "conflict_group": _text(o.conflict_group),
            "recognition_run_id": _id(o.recognition_run_id),
        }
    )


@persisted_data_boundary
def candidate_from_json(payload: str) -> FieldCandidate:
    d = loads(payload)
    try:
        conf = Confidence(Decimal(d["confidence"]))
    except Exception:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None
    return FieldCandidate(
        req_id(d["id"]),
        parse_field_ref(d["field_ref"]),
        parse_text(NonEmptyText, d["raw_value"]),
        parse_text(NonEmptyText, d.get("normalized_value")),
        parse_enum(CandidateSourceType, d["source_type"]),
        conf,
        parse_text(NonEmptyText, d.get("source_region")),
        tuple(NonEmptyText(x) for x in d["validation_results"]),
        parse_text(NonEmptyText, d.get("conflict_group")),
        parse_id(d.get("recognition_run_id")),
    )


def _verified_to_dict(o: VerifiedField) -> dict[str, Any]:
    return {
        "field_ref": _field_ref(o.field_ref),
        "value": _text(o.value),
        "status": o.status.value,
        "actor": _actor(o.actor),
        "timestamp": None if o.timestamp is None else utc_iso(o.timestamp),
        "source_candidate_id": _id(o.source_candidate_id),
        "override_reason": _text(o.override_reason),
    }


def _verified_from_dict(d: dict[str, Any]) -> VerifiedField:
    return VerifiedField(
        parse_field_ref(d["field_ref"]),
        parse_text(NonEmptyText, d.get("value")),
        parse_enum(VerificationStatus, d["status"]),
        parse_actor(d.get("actor")),
        None if d.get("timestamp") is None else parse_datetime(d["timestamp"]),
        parse_id(d.get("source_candidate_id")),
        parse_text(NonEmptyText, d.get("override_reason")),
    )


def _assignment_to_dict(o: ParticipantAssignment) -> dict[str, Any]:
    return {
        "person_id": str(o.person_id),
        "tractor_id": str(o.tractor_id),
        "trailer_id": _id(o.trailer_id),
        "pass_type": _text(o.pass_type),
        "position": _text(o.position),
        "organization": _text(o.organization),
    }


def _assignment_from_dict(d: dict[str, Any]) -> ParticipantAssignment:
    return ParticipantAssignment(
        req_id(d["person_id"]),
        req_id(d["tractor_id"]),
        parse_id(d.get("trailer_id")),
        parse_text(NonEmptyText, d.get("pass_type")),
        parse_text(NonEmptyText, d.get("position")),
        parse_text(NonEmptyText, d.get("organization")),
    )


def _issue_to_dict(o: ValidationIssue) -> dict[str, Any]:
    return {
        "code": _text(o.code),
        "message": _text(o.message),
        "blocking": o.blocking,
        "field_ref": None if o.field_ref is None else _field_ref(o.field_ref),
    }


def _issue_from_dict(d: dict[str, Any]) -> ValidationIssue:
    blocking = d.get("blocking")
    if not isinstance(blocking, bool):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return ValidationIssue(
        NonEmptyText(d["code"]),
        NonEmptyText(d["message"]),
        blocking,
        None if d.get("field_ref") is None else parse_field_ref(d["field_ref"]),
    )


def application_to_json(o: Application) -> str:
    return dumps(
        {
            "id": str(o.id),
            "batch_id": str(o.batch_id),
            "terminal_code": _enum(o.terminal_code),
            "assignments": [_assignment_to_dict(x) for x in o.assignments],
            "verified_fields": [_verified_to_dict(x) for x in o.verified_fields],
            "validation_issues": [_issue_to_dict(x) for x in o.validation_report.issues],
            "status": o.status.value,
            "created_by": _actor(o.created_by),
            "created_at": utc_iso(o.created_at),
            "updated_at": utc_iso(o.updated_at),
        }
    )


@persisted_data_boundary
def application_from_json(payload: str) -> Application:
    d = loads(payload)
    created_by = parse_actor(d["created_by"])
    if created_by is None:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return Application(
        req_id(d["id"]),
        req_id(d["batch_id"]),
        parse_enum(TerminalCode, d.get("terminal_code")),
        tuple(_assignment_from_dict(x) for x in d["assignments"]),
        tuple(_verified_from_dict(x) for x in d["verified_fields"]),
        ValidationReport(tuple(_issue_from_dict(x) for x in d["validation_issues"])),
        parse_enum(ApplicationStatus, d["status"]),
        created_by,
        parse_datetime(d["created_at"]),
        parse_datetime(d["updated_at"]),
    )


def snapshot_to_json(o: ApplicationSnapshot) -> str:
    return dumps(
        {
            "id": str(o.id),
            "application_id": str(o.application_id),
            "terminal_code": o.terminal_code.value,
            "template_version": _text(o.template_version),
            "rules_version": _text(o.rules_version),
            "created_by": _actor(o.created_by),
            "created_at": utc_iso(o.created_at),
            "payload": o.payload.as_dict(),
            "canonical_json": o.payload.canonical_json,
            "document_artifact_refs": [str(x) for x in o.document_artifact_refs],
            "sha256": o.sha256,
        }
    )


@persisted_data_boundary
def snapshot_from_json(payload: str) -> ApplicationSnapshot:
    d = loads(payload)
    sp = SnapshotPayload(d["payload"])
    if sp.canonical_json != d.get("canonical_json"):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    created_by = parse_actor(d["created_by"])
    if created_by is None:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return rehydrate_application_snapshot(
        snapshot_id=req_id(d["id"]),
        application_id=req_id(d["application_id"]),
        terminal_code=parse_enum(TerminalCode, d["terminal_code"]),
        template_version=NonEmptyText(d["template_version"]),
        rules_version=NonEmptyText(d["rules_version"]),
        created_by=created_by,
        created_at=parse_datetime(d["created_at"]),
        payload=sp,
        document_artifact_refs=tuple(req_id(x) for x in d["document_artifact_refs"]),
        sha256=d["sha256"],
    )


def application_scalar_to_json(o: Application) -> str:
    return dumps(
        {
            "id": str(o.id),
            "batch_id": str(o.batch_id),
            "terminal_code": _enum(o.terminal_code),
            "status": o.status.value,
            "created_by": _actor(o.created_by),
            "created_at": utc_iso(o.created_at),
            "updated_at": utc_iso(o.updated_at),
        }
    )


@persisted_data_boundary
def application_from_components(
    payload: str,
    assignments: tuple[ParticipantAssignment, ...],
    verified_fields: tuple[VerifiedField, ...],
    issues: tuple[ValidationIssue, ...],
) -> Application:
    d = loads(payload)
    created_by = parse_actor(d["created_by"])
    if created_by is None:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return Application(
        req_id(d["id"]),
        req_id(d["batch_id"]),
        parse_enum(TerminalCode, d.get("terminal_code")),
        assignments,
        verified_fields,
        ValidationReport(issues),
        parse_enum(ApplicationStatus, d["status"]),
        created_by,
        parse_datetime(d["created_at"]),
        parse_datetime(d["updated_at"]),
    )


@persisted_data_boundary
def assignment_from_json(payload: str) -> ParticipantAssignment:
    return _assignment_from_dict(loads(payload))


@persisted_data_boundary
def verified_field_from_json(payload: str) -> VerifiedField:
    return _verified_from_dict(loads(payload))


@persisted_data_boundary
def validation_issue_from_json(payload: str) -> ValidationIssue:
    return _issue_from_dict(loads(payload))


def application_columns(o: Application) -> tuple[str, str, str | None, str, str, str, str, str]:
    return (
        str(o.id),
        str(o.batch_id),
        _enum(o.terminal_code),
        o.status.value,
        str(o.created_by.actor_id),
        o.created_by.kind.value,
        utc_iso(o.created_at),
        utc_iso(o.updated_at),
    )


@persisted_data_boundary
def application_from_row(
    row: tuple[str, str, str | None, str, str, str, str, str],
    assignments: tuple[ParticipantAssignment, ...],
    verified_fields: tuple[VerifiedField, ...],
    issues: tuple[ValidationIssue, ...],
) -> Application:
    try:
        created_by = ActorRef(req_id(row[4]), parse_enum(ActorKind, row[5]))
        return Application(
            req_id(row[0]),
            req_id(row[1]),
            parse_enum(TerminalCode, row[2]),
            assignments,
            verified_fields,
            ValidationReport(issues),
            parse_enum(ApplicationStatus, row[3]),
            created_by,
            parse_datetime(row[6]),
            parse_datetime(row[7]),
        )
    except (IndexError, TypeError, ValueError, DomainError):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


def snapshot_columns(
    o: ApplicationSnapshot,
) -> tuple[str, str, str, str, str, str, str, str, str, str]:
    return (
        str(o.id),
        str(o.application_id),
        o.terminal_code.value,
        o.template_version.value,
        o.rules_version.value,
        str(o.created_by.actor_id),
        o.created_by.kind.value,
        utc_iso(o.created_at),
        o.payload.canonical_json,
        o.sha256,
    )


@persisted_data_boundary
def snapshot_from_row(
    row: tuple[str, str, str, str, str, str, str, str, str, str],
    artifact_refs: tuple[EntityId, ...],
) -> ApplicationSnapshot:
    try:
        payload_data = json.loads(row[8])
        if not isinstance(payload_data, dict):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        payload = SnapshotPayload(payload_data)
        if payload.canonical_json != row[8]:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return rehydrate_application_snapshot(
            snapshot_id=req_id(row[0]),
            application_id=req_id(row[1]),
            terminal_code=parse_enum(TerminalCode, row[2]),
            template_version=NonEmptyText(row[3]),
            rules_version=NonEmptyText(row[4]),
            created_by=ActorRef(req_id(row[5]), parse_enum(ActorKind, row[6])),
            created_at=parse_datetime(row[7]),
            payload=payload,
            document_artifact_refs=artifact_refs,
            sha256=row[9],
        )
    except (json.JSONDecodeError, IndexError, TypeError, ValueError, DomainError):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None


_STORED_ARTIFACT_FIELDS = frozenset(
    {
        "artifact_id",
        "artifact_kind",
        "object_generation",
        "plaintext_length",
        "plaintext_sha256",
        "ciphertext_sha256",
        "key_version",
        "storage_format_version",
        "created_at",
    }
)


def _require_json_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return value


def stored_artifact_to_json(o: StoredArtifactRecord) -> str:
    return dumps(
        {
            "artifact_id": str(o.artifact_id),
            "artifact_kind": o.artifact_kind.value,
            "object_generation": o.object_generation,
            "plaintext_length": o.plaintext_length,
            "plaintext_sha256": o.plaintext_sha256,
            "ciphertext_sha256": o.ciphertext_sha256,
            "key_version": o.key_version,
            "storage_format_version": o.storage_format_version,
            "created_at": utc_iso(o.created_at),
        }
    )


@persisted_data_boundary
def stored_artifact_from_json(payload: str) -> StoredArtifactRecord:
    d = loads(payload)
    if set(d) != _STORED_ARTIFACT_FIELDS:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return StoredArtifactRecord(
        artifact_id=req_id(d["artifact_id"]),
        artifact_kind=parse_enum(ArtifactKind, d["artifact_kind"]),
        object_generation=_require_json_int(d["object_generation"]),
        plaintext_length=_require_json_int(d["plaintext_length"]),
        plaintext_sha256=d["plaintext_sha256"],
        ciphertext_sha256=d["ciphertext_sha256"],
        key_version=_require_json_int(d["key_version"]),
        storage_format_version=_require_json_int(d["storage_format_version"]),
        created_at=parse_datetime(d["created_at"]),
    )


def stored_artifact_columns(
    o: StoredArtifactRecord,
) -> tuple[str, str, int, int, str, str, int, int, str]:
    return (
        str(o.artifact_id),
        o.artifact_kind.value,
        o.object_generation,
        o.plaintext_length,
        o.plaintext_sha256,
        o.ciphertext_sha256,
        o.key_version,
        o.storage_format_version,
        utc_iso(o.created_at),
    )


_AUDIT_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "occurred_at",
        "actor",
        "action_code",
        "subject_type",
        "subject_id",
        "field_key",
        "before",
        "after",
        "reason_code",
        "correlation_id",
    }
)
_AUDIT_SUMMARY_FIELDS = frozenset({"classification", "display_value", "was_present"})


def _audit_summary(value: AuditValueSummary | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "classification": value.classification.value,
        "display_value": value.display_value,
        "was_present": value.was_present,
    }


def _parse_audit_summary(value: object) -> AuditValueSummary | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _AUDIT_SUMMARY_FIELDS:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return AuditValueSummary(
        parse_enum(AuditValueClassification, value["classification"]),
        value["display_value"],
        value["was_present"],
    )


def audit_event_to_json(event: AuditEvent) -> str:
    if not isinstance(event, AuditEvent):
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    return dumps(
        {
            "event_id": str(event.event_id),
            "occurred_at": utc_iso(event.occurred_at),
            "actor": _actor(event.actor),
            "action_code": event.action_code.value,
            "subject_type": event.subject_type.value,
            "subject_id": str(event.subject_id),
            "field_key": None if event.field_key is None else event.field_key.value,
            "before": _audit_summary(event.before),
            "after": _audit_summary(event.after),
            "reason_code": None if event.reason_code is None else event.reason_code.value,
            "correlation_id": _id(event.correlation_id),
        }
    )


@persisted_data_boundary
def audit_event_from_json(payload: str) -> AuditEvent:
    d = loads(payload)
    if set(d) != _AUDIT_EVENT_FIELDS:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    actor = parse_actor(d["actor"])
    if actor is None:
        raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
    field_key = d["field_key"]
    reason = d["reason_code"]
    return AuditEvent(
        event_id=req_id(d["event_id"]),
        occurred_at=parse_datetime(d["occurred_at"]),
        actor=actor,
        action_code=parse_enum(AuditAction, d["action_code"]),
        subject_type=parse_enum(AuditSubjectType, d["subject_type"]),
        subject_id=req_id(d["subject_id"]),
        field_key=None if field_key is None else FieldKey(field_key),
        before=_parse_audit_summary(d["before"]),
        after=_parse_audit_summary(d["after"]),
        reason_code=None if reason is None else AuditReasonCode(reason),
        correlation_id=parse_id(d["correlation_id"]),
    )


def audit_event_columns(event: AuditEvent) -> tuple[object, ...]:
    def parts(summary: AuditValueSummary | None) -> tuple[object, object, object]:
        if summary is None:
            return (None, None, None)
        return (
            summary.classification.value,
            1 if summary.was_present else 0,
            summary.display_value,
        )

    return (
        str(event.event_id),
        utc_iso(event.occurred_at),
        str(event.actor.actor_id),
        event.actor.kind.value,
        event.action_code.value,
        event.subject_type.value,
        str(event.subject_id),
        None if event.field_key is None else event.field_key.value,
        *parts(event.before),
        *parts(event.after),
        None if event.reason_code is None else event.reason_code.value,
        None if event.correlation_id is None else str(event.correlation_id),
    )
