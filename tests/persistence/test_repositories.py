from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
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
    MigrationDocument,
    NonEmptyText,
    OwnerKind,
    OwnerRef,
    ParticipantAssignment,
    Person,
    SnapshotPayload,
    Terminal,
    TerminalCode,
    ValidationIssue,
    ValidationReport,
    Vehicle,
    VehicleRole,
    VerificationStatus,
    VerifiedField,
    create_application_snapshot,
)
from document_intake.persistence.database import (
    ApplicationRepo,
    CandidateRepo,
    DocumentRepo,
    IdentityRepo,
    MigrationRepo,
    PersonRepo,
    SnapshotRepo,
    TerminalRepo,
    VehicleRepo,
)
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import APPLICATION_ID
from document_intake.persistence.migrations.v0001_initial import MIGRATION

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


def eid(value: int) -> EntityId:
    return EntityId(UUID(int=value))


def actor(value: int = 900, kind: ActorKind = ActorKind.OPERATOR) -> ActorRef:
    return ActorRef(eid(value), kind)


def field_ref(entity: int = 1, key: str = "identity_document.number") -> FieldRef:
    return FieldRef(eid(entity), FieldKey(key))


class FakeUow:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.closed = False

    def _connection(self) -> sqlite3.Connection:
        if self.closed:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        return self.conn


def migrated_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    for statement in MIGRATION.statements:
        conn.execute(statement)
    conn.execute(
        "INSERT INTO schema_migrations(version, name, checksum, applied_at_utc) "
        "VALUES (?, ?, ?, ?)",
        (MIGRATION.version, MIGRATION.name, MIGRATION.checksum, "2026-07-19T00:00:00Z"),
    )
    conn.execute(f"PRAGMA user_version = {MIGRATION.version}")
    conn.execute("COMMIT")
    return conn


def seed_person_vehicle_terminal(uow: FakeUow) -> None:
    PersonRepo(uow).add(person())
    VehicleRepo(uow).add(vehicle(eid(20), VehicleRole.TRACTOR))
    VehicleRepo(uow).add(vehicle(eid(21), VehicleRole.TRAILER))
    TerminalRepo(uow).add(terminal())


def person() -> Person:
    return Person(
        id=eid(1),
        full_name_cyrillic=NonEmptyText("Иван Тестовый"),
        full_name_latin=NonEmptyText("Ivan Unicode-Test"),
        birth_date=date(1991, 2, 3),
        birth_place=NonEmptyText("Fiction City; SELECT * FROM persons"),
        sex=NonEmptyText("M"),
        citizenship=CountryCode("KG"),
        phone=IdentifierText("000123456789"),
        registration_address=NonEmptyText("Synthetic Address, Apt 'Quote'"),
    )


def identity_document() -> IdentityDocument:
    return IdentityDocument(
        id=eid(10),
        person_id=eid(1),
        document_type=DocumentType.PASSPORT,
        series=IdentifierText("AA"),
        number=IdentifierText("000012345"),
        full_number=IdentifierText("AA000012345"),
        issue_date=date(2020, 1, 2),
        expiry_date=date(2030, 1, 2),
        issuer=NonEmptyText('Issuer "Quoted"'),
        division_code=IdentifierText("001-002"),
        personal_number=IdentifierText("PN0000001"),
        mrz_raw=NonEmptyText("SYNTHETICMRZ"),
        mrz_validation_status=NonEmptyText("VALID"),
    )


def migration_document() -> MigrationDocument:
    return MigrationDocument(
        id=eid(11),
        person_id=eid(1),
        series=IdentifierText("MC"),
        number=IdentifierText("0000999"),
        arrival_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        declared_identity_number=IdentifierText("AA000012345"),
        declared_citizenship=CountryCode("KG"),
        stamp_data=NonEmptyText("Synthetic stamp"),
        related_passport_id=eid(10),
    )


def vehicle(identifier: EntityId | None = None, role: VehicleRole = VehicleRole.TRACTOR) -> Vehicle:
    identifier = eid(20) if identifier is None else identifier
    return Vehicle(
        id=identifier,
        role=role,
        registration_number=IdentifierText("00A000"),
        vin=IdentifierText("VIN00000000000001"),
        chassis_number=IdentifierText("CHASSIS001"),
        body_number=IdentifierText("BODY001"),
        make=NonEmptyText("Make Unicode Ж"),
        model=NonEmptyText("Model; DROP TABLE vehicles;"),
        year=2024,
        color=NonEmptyText("Blue"),
        vehicle_type=NonEmptyText("Truck"),
        max_mass=12000,
        unladen_mass=6000,
        owner=OwnerRef(OwnerKind.PERSON, eid(1)),
        registration_document_id=eid(40),
    )


def terminal() -> Terminal:
    return Terminal(
        code=TerminalCode.TSP,
        display_name=NonEmptyText("TSP Synthetic"),
        adapter_version=NonEmptyText("adapter-v1"),
        template_version=NonEmptyText("template-v1"),
        template_checksum=NonEmptyText("checksum-v1"),
        rules_version=NonEmptyText("rules-v1"),
        is_active=True,
    )


def document() -> Document:
    return Document(
        id=eid(40),
        document_type=DocumentType.DRIVER_LICENSE,
        workflow_status=DocumentWorkflowStatus.VERIFIED,
        country_code=CountryCode("KG"),
        template_version=NonEmptyText("doc-template"),
        owner_ref=OwnerRef(OwnerKind.PERSON, eid(1)),
        side_ids=(eid(41), eid(42)),
        prepared_artifact_id=eid(43),
    )


def candidate() -> FieldCandidate:
    return FieldCandidate(
        id=eid(50),
        field_ref=field_ref(),
        raw_value=NonEmptyText("000012345; SELECT 1"),
        normalized_value=NonEmptyText("000012345"),
        source_type=CandidateSourceType.VISUAL_OCR,
        confidence=Confidence(Decimal("0.8700")),
        source_region=NonEmptyText("region-1"),
        validation_results=(NonEmptyText("passes-leading-zero"), NonEmptyText("unicode-ж")),
        conflict_group=NonEmptyText("group-1"),
        recognition_run_id=eid(60),
    )


def application(status: ApplicationStatus = ApplicationStatus.READY_FOR_SNAPSHOT) -> Application:
    verified = VerifiedField(
        field_ref(),
        NonEmptyText("000012345"),
        VerificationStatus.VERIFIED,
        actor(),
        NOW,
        source_candidate_id=eid(50),
    )
    issue = ValidationIssue(
        NonEmptyText("safe_code"), NonEmptyText("safe message"), False, field_ref()
    )
    return Application(
        id=eid(70),
        batch_id=eid(71),
        terminal_code=TerminalCode.TSP,
        assignments=(
            ParticipantAssignment(
                person_id=eid(1),
                tractor_id=eid(20),
                trailer_id=eid(21),
                pass_type=NonEmptyText("driver"),
                position=NonEmptyText("operator"),
                organization=NonEmptyText("synthetic org"),
            ),
        ),
        verified_fields=(verified,),
        validation_report=ValidationReport((issue,)),
        status=status,
        created_by=actor(),
        created_at=NOW,
        updated_at=NOW,
    )


def snapshot(app: Application):
    return create_application_snapshot(
        app,
        snapshot_id=eid(80),
        payload=SnapshotPayload({"safe": "payload", "order": [1, 2]}),
        document_artifact_refs=(eid(81), eid(82)),
        template_version=NonEmptyText("template-v1"),
        rules_version=NonEmptyText("rules-v1"),
        created_by=actor(),
        created_at=NOW,
        required_critical_fields=frozenset({field_ref()}),
    )


def test_every_repository_round_trip_and_ordered_children() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    persons = PersonRepo(uow)
    persons.add(person())
    assert persons.get(eid(1)) == person()
    assert persons.list_all() == (person(),)

    identities = IdentityRepo(uow)
    identities.add(identity_document())
    assert identities.get(eid(10)) == identity_document()
    assert identities.list_by_person(eid(1))[0].number == IdentifierText("000012345")

    migrations = MigrationRepo(uow)
    migrations.add(migration_document())
    assert migrations.get(eid(11)) == migration_document()
    assert migrations.list_by_person(eid(1)) == (migration_document(),)

    vehicles = VehicleRepo(uow)
    tractor = vehicle(eid(20), VehicleRole.TRACTOR)
    trailer = vehicle(eid(21), VehicleRole.TRAILER)
    vehicles.add(tractor)
    vehicles.add(trailer)
    assert vehicles.get(eid(20)) == tractor
    assert vehicles.list_all() == (tractor, trailer)

    terminals = TerminalRepo(uow)
    terminals.add(terminal())
    assert terminals.get(TerminalCode.TSP) == terminal()
    assert terminals.list_active() == (terminal(),)

    documents = DocumentRepo(uow)
    documents.add(document())
    assert documents.get(eid(40)) == document()
    assert documents.list_by_owner(OwnerRef(OwnerKind.PERSON, eid(1))) == (document(),)
    assert [
        row[0] for row in conn.execute("SELECT side_id FROM document_sides ORDER BY order_index")
    ] == [
        str(eid(41)),
        str(eid(42)),
    ]

    candidates = CandidateRepo(uow)
    candidates.add(candidate())
    assert candidates.get(eid(50)) == candidate()
    assert candidates.list_for_field(field_ref()) == (candidate(),)
    assert conn.execute("SELECT confidence FROM field_candidates").fetchone()[0] == "0.8700"


def test_application_repository_uses_structured_children_and_round_trips() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    seed_person_vehicle_terminal(uow)
    CandidateRepo(uow).add(candidate())
    repo = ApplicationRepo(uow)
    app = application()
    repo.add(app)
    assert repo.get(eid(70)) == app
    assert conn.execute("SELECT count(*) FROM application_assignments").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM application_verified_fields").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM application_validation_issues").fetchone()[0] == 1
    assert "assignments" not in conn.execute("SELECT payload FROM applications").fetchone()[0]


def test_application_update_replaces_children_inside_transaction() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    seed_person_vehicle_terminal(uow)
    CandidateRepo(uow).add(candidate())
    repo = ApplicationRepo(uow)
    app = application()
    repo.add(app)
    updated = Application(
        id=app.id,
        batch_id=app.batch_id,
        terminal_code=app.terminal_code,
        assignments=(),
        verified_fields=app.verified_fields,
        validation_report=ValidationReport(),
        status=app.status,
        created_by=app.created_by,
        created_at=app.created_at,
        updated_at=datetime(2026, 7, 19, 13, 0, tzinfo=UTC),
    )
    conn.execute("BEGIN IMMEDIATE")
    repo.update(updated)
    conn.execute("ROLLBACK")
    assert repo.get(eid(70)) == app


def test_snapshot_repository_round_trip_and_triggers() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    seed_person_vehicle_terminal(uow)
    CandidateRepo(uow).add(candidate())
    app = application()
    ApplicationRepo(uow).add(app)
    snap = snapshot(app)
    repo = SnapshotRepo(uow)
    repo.add(snap)
    assert repo.get(eid(80)) == snap
    assert repo.list_by_application(eid(70)) == (snap,)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE application_snapshots SET sha256='safe' WHERE id=?", (str(eid(80)),))
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM application_snapshots WHERE id=?", (str(eid(80)),))
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(
            "UPDATE application_snapshot_artifact_refs SET artifact_ref=? WHERE snapshot_id=?",
            (str(eid(83)), str(eid(80))),
        )
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(
            "DELETE FROM application_snapshot_artifact_refs WHERE snapshot_id=?", (str(eid(80)),)
        )


def test_duplicate_missing_invalid_persisted_and_closed_errors_are_safe() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    repo = PersonRepo(uow)
    repo.add(person())
    with pytest.raises(PersistenceError) as duplicate:
        repo.add(person())
    assert duplicate.value.code == PersistenceErrorCode.ENTITY_ALREADY_EXISTS
    with pytest.raises(PersistenceError) as missing:
        repo.update(Person(eid(999), full_name_latin=NonEmptyText("Missing")))
    assert missing.value.code == PersistenceErrorCode.ENTITY_NOT_FOUND
    conn.execute("UPDATE persons SET payload=? WHERE id=?", ('{"id":"not-a-uuid"}', str(eid(1))))
    with pytest.raises(PersistenceError) as invalid:
        repo.get(eid(1))
    assert invalid.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID
    uow.closed = True
    with pytest.raises(PersistenceError) as closed:
        repo.list_all()
    assert closed.value.code == PersistenceErrorCode.UOW_CLOSED
