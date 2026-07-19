from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from document_intake.domain import (
    ActorKind,
    ActorRef,
    Application,
    ApplicationSnapshot,
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
from document_intake.persistence import serialization as ser
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


def second_person() -> Person:
    return Person(id=eid(2), full_name_latin=NonEmptyText("Second Synthetic"))


def second_identity_document() -> IdentityDocument:
    return replace(identity_document(), id=eid(12), person_id=eid(2))


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


def second_application() -> Application:
    source = application()
    return Application(
        id=eid(73),
        batch_id=eid(74),
        terminal_code=source.terminal_code,
        assignments=source.assignments,
        verified_fields=source.verified_fields,
        validation_report=source.validation_report,
        status=source.status,
        created_by=source.created_by,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def snapshot_with_refs(app: Application, snapshot_id: EntityId, refs: tuple[EntityId, ...]):
    return create_application_snapshot(
        app,
        snapshot_id=snapshot_id,
        payload=SnapshotPayload({"safe": "payload", "order": [1, 2]}),
        document_artifact_refs=refs,
        template_version=NonEmptyText("template-v1"),
        rules_version=NonEmptyText("rules-v1"),
        created_by=actor(),
        created_at=NOW,
        required_critical_fields=frozenset({field_ref()}),
    )


def snapshot(app: Application):
    return snapshot_with_refs(app, eid(80), (eid(81), eid(82)))


def stored_snapshot(
    refs: tuple[EntityId, ...] = (eid(81), eid(82)),
) -> tuple[sqlite3.Connection, SnapshotRepo, ApplicationSnapshot]:
    conn = migrated_connection()
    uow = FakeUow(conn)
    seed_person_vehicle_terminal(uow)
    CandidateRepo(uow).add(candidate())
    app = application()
    ApplicationRepo(uow).add(app)
    snap = snapshot_with_refs(app, eid(80), refs)
    repo = SnapshotRepo(uow)
    repo.add(snap)
    return conn, repo, snap


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


def test_vehicle_registration_document_id_is_an_opaque_round_trip_reference() -> None:
    conn = migrated_connection()
    repo = VehicleRepo(FakeUow(conn))
    entity = vehicle()
    assert conn.execute("SELECT count(*) FROM documents").fetchone()[0] == 0
    repo.add(entity)
    stored = repo.get(entity.id)
    assert stored == entity
    assert stored is not None
    assert stored.registration_document_id == eid(40)


def test_updates_move_relation_projections_and_queries_with_payload() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    persons = PersonRepo(uow)
    persons.add(person())
    persons.add(second_person())

    identities = IdentityRepo(uow)
    identities.add(identity_document())
    identities.add(second_identity_document())
    moved_identity = replace(identity_document(), person_id=eid(2))
    identities.update(moved_identity)
    assert identities.get(eid(10)) == moved_identity
    assert identities.list_by_person(eid(1)) == ()
    assert identities.list_by_person(eid(2)) == (moved_identity, second_identity_document())

    migrations = MigrationRepo(uow)
    migrations.add(migration_document())
    moved_migration = replace(migration_document(), person_id=eid(2), related_passport_id=eid(12))
    migrations.update(moved_migration)
    assert migrations.get(eid(11)) == moved_migration
    assert migrations.list_by_person(eid(1)) == ()
    assert migrations.list_by_person(eid(2)) == (moved_migration,)

    vehicles = VehicleRepo(uow)
    vehicles.add(vehicle())
    documents = DocumentRepo(uow)
    documents.add(document())
    moved_document = Document(
        id=document().id,
        document_type=document().document_type,
        workflow_status=document().workflow_status,
        country_code=document().country_code,
        template_version=document().template_version,
        owner_ref=OwnerRef(OwnerKind.VEHICLE, eid(20)),
        side_ids=(eid(42), eid(41)),
        prepared_artifact_id=document().prepared_artifact_id,
    )
    documents.update(moved_document)
    assert documents.get(eid(40)) == moved_document
    assert documents.list_by_owner(OwnerRef(OwnerKind.PERSON, eid(1))) == ()
    assert documents.list_by_owner(OwnerRef(OwnerKind.VEHICLE, eid(20))) == (moved_document,)

    candidates = CandidateRepo(uow)
    candidates.add(candidate())
    moved_candidate = replace(
        candidate(),
        field_ref=field_ref(2, "identity_document.full_number"),
        validation_results=(NonEmptyText("replacement-result"),),
    )
    candidates.update(moved_candidate)
    assert candidates.get(eid(50)) == moved_candidate
    assert candidates.list_for_field(field_ref()) == ()
    assert candidates.list_for_field(moved_candidate.field_ref) == (moved_candidate,)


@pytest.mark.parametrize(
    ("tamper", "read"),
    [
        (
            lambda c: c.execute(
                "UPDATE identity_documents SET person_id=? WHERE id=?",
                (str(eid(2)), str(eid(10))),
            ),
            lambda u: IdentityRepo(u).get(eid(10)),
        ),
        (
            lambda c: c.execute(
                "UPDATE documents SET owner_kind=?, owner_id=? WHERE id=?",
                (OwnerKind.VEHICLE.value, str(eid(20)), str(eid(40))),
            ),
            lambda u: DocumentRepo(u).get(eid(40)),
        ),
        (
            lambda c: c.execute(
                "UPDATE field_candidate_validation_results SET result=? "
                "WHERE candidate_id=? AND order_index=0",
                ("tampered-result", str(eid(50))),
            ),
            lambda u: CandidateRepo(u).get(eid(50)),
        ),
        (
            lambda c: c.execute(
                "UPDATE applications SET status=? WHERE id=?",
                (ApplicationStatus.DRAFT.value, str(eid(70))),
            ),
            lambda u: ApplicationRepo(u).get(eid(70)),
        ),
    ],
)
def test_projection_tampering_is_rejected(tamper, read) -> None:  # type: ignore[no-untyped-def]
    conn = migrated_connection()
    uow = FakeUow(conn)
    seed_person_vehicle_terminal(uow)
    PersonRepo(uow).add(second_person())
    IdentityRepo(uow).add(identity_document())
    DocumentRepo(uow).add(document())
    CandidateRepo(uow).add(candidate())
    ApplicationRepo(uow).add(application())
    tamper(conn)
    with pytest.raises(PersistenceError) as excinfo:
        read(uow)
    assert excinfo.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_relation_list_queries_reject_projection_tampering_for_old_and_new_keys() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    seed_person_vehicle_terminal(uow)
    PersonRepo(uow).add(second_person())

    identities = IdentityRepo(uow)
    identities.add(identity_document())
    identities.add(second_identity_document())
    conn.execute(
        "UPDATE identity_documents SET person_id=? WHERE id=?",
        (str(eid(2)), str(eid(10))),
    )
    for person_id in (eid(1), eid(2)):
        with pytest.raises(PersistenceError) as invalid:
            identities.list_by_person(person_id)
        assert invalid.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID

    migrations = MigrationRepo(uow)
    migrations.add(migration_document())
    conn.execute(
        "UPDATE migration_documents SET person_id=? WHERE id=?",
        (str(eid(2)), str(eid(11))),
    )
    for person_id in (eid(1), eid(2)):
        with pytest.raises(PersistenceError) as invalid:
            migrations.list_by_person(person_id)
        assert invalid.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID

    documents = DocumentRepo(uow)
    documents.add(document())
    original_owner = OwnerRef(OwnerKind.PERSON, eid(1))
    tampered_owner = OwnerRef(OwnerKind.VEHICLE, eid(20))
    conn.execute(
        "UPDATE documents SET owner_kind=?, owner_id=? WHERE id=?",
        (tampered_owner.owner_kind.value, str(tampered_owner.owner_id), str(eid(40))),
    )
    for owner in (original_owner, tampered_owner):
        with pytest.raises(PersistenceError) as invalid:
            documents.list_by_owner(owner)
        assert invalid.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID

    candidates = CandidateRepo(uow)
    candidates.add(candidate())
    original_field = field_ref()
    tampered_field = field_ref(2, "identity_document.full_number")
    conn.execute(
        "UPDATE field_candidates SET field_entity_id=?, field_key=? WHERE id=?",
        (
            str(tampered_field.entity_id),
            tampered_field.field_key.value,
            str(eid(50)),
        ),
    )
    for field in (original_field, tampered_field):
        with pytest.raises(PersistenceError) as invalid:
            candidates.list_for_field(field)
        assert invalid.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_terminal_list_rejects_projection_tampering_in_both_directions() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    terminals = TerminalRepo(uow)
    terminals.add(terminal())
    inactive = replace(terminal(), code=TerminalCode.VISITORS, is_active=False)
    terminals.add(inactive)

    conn.execute("UPDATE terminals SET is_active=0 WHERE code=?", (TerminalCode.TSP.value,))
    with pytest.raises(PersistenceError) as hidden_active:
        terminals.list_active()
    assert hidden_active.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID

    conn.execute("UPDATE terminals SET is_active=1 WHERE code=?", (TerminalCode.TSP.value,))
    conn.execute("UPDATE terminals SET is_active=1 WHERE code=?", (TerminalCode.VISITORS.value,))
    with pytest.raises(PersistenceError) as false_active:
        terminals.list_active()
    assert false_active.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_snapshot_list_rejects_application_projection_tampering_for_both_keys() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    seed_person_vehicle_terminal(uow)
    CandidateRepo(uow).add(candidate())
    app = application()
    other_app = second_application()
    ApplicationRepo(uow).add(app)
    ApplicationRepo(uow).add(other_app)
    snap = snapshot(app)
    columns = list(ser.snapshot_columns(snap))
    columns[1] = str(other_app.id)
    conn.execute(
        "INSERT INTO application_snapshots"
        "(id, application_id, terminal_code, template_version, rules_version, "
        "created_by_actor_id, created_by_actor_kind, created_at_utc, payload_json, "
        "sha256, expected_artifact_ref_count, payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (*columns, len(snap.document_artifact_refs), ser.snapshot_to_json(snap)),
    )
    for index, artifact_ref in enumerate(snap.document_artifact_refs):
        conn.execute(
            "INSERT INTO application_snapshot_artifact_refs"
            "(snapshot_id, order_index, artifact_ref) VALUES (?, ?, ?)",
            (str(snap.id), index, str(artifact_ref)),
        )

    repo = SnapshotRepo(uow)
    for application_id in (app.id, other_app.id):
        with pytest.raises(PersistenceError) as invalid:
            repo.list_by_application(application_id)
        assert invalid.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID


def test_child_projection_failure_rolls_back_complete_repository_update() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    PersonRepo(uow).add(person())
    document_repo = DocumentRepo(uow)
    document_repo.add(document())
    conn.execute(
        f"CREATE TRIGGER synthetic_side_failure BEFORE INSERT ON document_sides "
        f"WHEN NEW.side_id = '{eid(99)}' BEGIN SELECT RAISE(ABORT, 'synthetic'); END"
    )
    changed_document = Document(
        id=document().id,
        document_type=document().document_type,
        workflow_status=document().workflow_status,
        owner_ref=OwnerRef(OwnerKind.VEHICLE, eid(20)),
        side_ids=(eid(41), eid(99)),
    )
    with pytest.raises(PersistenceError) as document_error:
        document_repo.update(changed_document)
    assert document_error.value.code == PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    assert document_repo.get(eid(40)) == document()

    candidate_repo = CandidateRepo(uow)
    candidate_repo.add(candidate())
    conn.execute(
        "CREATE TRIGGER synthetic_candidate_failure BEFORE INSERT "
        "ON field_candidate_validation_results WHEN NEW.result = 'synthetic-failure' "
        "BEGIN SELECT RAISE(ABORT, 'synthetic'); END"
    )
    changed_candidate = replace(
        candidate(), validation_results=(NonEmptyText("synthetic-failure"),)
    )
    with pytest.raises(PersistenceError) as candidate_error:
        candidate_repo.update(changed_candidate)
    assert candidate_error.value.code == PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    assert candidate_repo.get(eid(50)) == candidate()


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
    assert "payload" in [row[1] for row in conn.execute("PRAGMA table_info(applications)")]
    conn.execute("UPDATE applications SET status=? WHERE id=?", ("UNKNOWN_STATUS", str(eid(70))))
    with pytest.raises(PersistenceError) as invalid:
        repo.get(eid(70))
    assert invalid.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID
    assert "UNKNOWN_STATUS" not in str(invalid.value)


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

    PersonRepo(uow).add(second_person())
    moved_assignment = replace(app.assignments[0], person_id=eid(2), trailer_id=None)
    persisted_update = Application(
        id=app.id,
        batch_id=eid(72),
        terminal_code=app.terminal_code,
        assignments=(moved_assignment,),
        verified_fields=(),
        validation_report=ValidationReport(),
        status=ApplicationStatus.DRAFT,
        created_by=app.created_by,
        created_at=app.created_at,
        updated_at=datetime(2026, 7, 19, 14, 0, tzinfo=UTC),
    )
    repo.update(persisted_update)
    assert repo.get(eid(70)) == persisted_update
    assert conn.execute(
        "SELECT batch_id, status FROM applications WHERE id=?", (str(eid(70)),)
    ).fetchone() == (str(eid(72)), ApplicationStatus.DRAFT.value)
    assert conn.execute(
        "SELECT person_id, trailer_id FROM application_assignments WHERE application_id=?",
        (str(eid(70)),),
    ).fetchone() == (str(eid(2)), None)


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
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(
            "INSERT INTO application_snapshot_artifact_refs"
            "(snapshot_id, order_index, artifact_ref) VALUES (?,?,?)",
            (str(eid(80)), 2, str(eid(83))),
        )

    zero = snapshot_with_refs(application(), eid(90), ())
    repo.add(zero)
    assert repo.get(eid(90)) == zero
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(
            "INSERT INTO application_snapshot_artifact_refs"
            "(snapshot_id, order_index, artifact_ref) VALUES (?,?,?)",
            (str(eid(90)), 0, str(eid(91))),
        )


def test_duplicate_snapshot_repository_add_keeps_stable_error() -> None:
    _, repo, snap = stored_snapshot()
    with pytest.raises(PersistenceError) as duplicate:
        repo.add(snap)
    assert duplicate.value.code == PersistenceErrorCode.ENTITY_ALREADY_EXISTS


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_snapshot_parent_replace_forms_are_blocked(verb: str) -> None:
    conn, _, _ = stored_snapshot()
    row = conn.execute(
        "SELECT id, application_id, terminal_code, template_version, rules_version, "
        "created_by_actor_id, created_by_actor_kind, created_at_utc, payload_json, sha256, "
        "expected_artifact_ref_count, payload FROM application_snapshots WHERE id=?",
        (str(eid(80)),),
    ).fetchone()
    assert row is not None
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(
            f"{verb} INTO application_snapshots"
            "(id, application_id, terminal_code, template_version, rules_version, "
            "created_by_actor_id, created_by_actor_kind, created_at_utc, payload_json, "
            "sha256, expected_artifact_ref_count, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_zero_artifact_snapshot_parent_replace_forms_are_blocked(verb: str) -> None:
    conn, _, _ = stored_snapshot(())
    row = conn.execute(
        "SELECT id, application_id, terminal_code, template_version, rules_version, "
        "created_by_actor_id, created_by_actor_kind, created_at_utc, payload_json, sha256, "
        "expected_artifact_ref_count, payload FROM application_snapshots WHERE id=?",
        (str(eid(80)),),
    ).fetchone()
    assert row is not None
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(
            f"{verb} INTO application_snapshots"
            "(id, application_id, terminal_code, template_version, rules_version, "
            "created_by_actor_id, created_by_actor_kind, created_at_utc, payload_json, "
            "sha256, expected_artifact_ref_count, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )


@pytest.mark.parametrize("verb", ["INSERT OR REPLACE", "REPLACE"])
def test_snapshot_artifact_replace_forms_are_blocked(verb: str) -> None:
    conn, _, _ = stored_snapshot()
    row = conn.execute(
        "SELECT snapshot_id, order_index, artifact_ref "
        "FROM application_snapshot_artifact_refs WHERE snapshot_id=? AND order_index=0",
        (str(eid(80)),),
    ).fetchone()
    assert row is not None
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(
            f"{verb} INTO application_snapshot_artifact_refs"
            "(snapshot_id, order_index, artifact_ref) VALUES (?, ?, ?)",
            row,
        )


def test_incomplete_snapshot_projection_is_invalid_and_add_is_atomic() -> None:
    conn = migrated_connection()
    uow = FakeUow(conn)
    seed_person_vehicle_terminal(uow)
    CandidateRepo(uow).add(candidate())
    app = application()
    ApplicationRepo(uow).add(app)
    repo = SnapshotRepo(uow)
    incomplete = snapshot_with_refs(app, eid(84), (eid(85), eid(86)))
    conn.execute(
        "INSERT INTO application_snapshots"
        "(id, application_id, terminal_code, template_version, rules_version, "
        "created_by_actor_id, created_by_actor_kind, created_at_utc, payload_json, "
        "sha256, expected_artifact_ref_count, payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            *ser.snapshot_columns(incomplete),
            len(incomplete.document_artifact_refs),
            ser.snapshot_to_json(incomplete),
        ),
    )
    with pytest.raises(PersistenceError) as invalid:
        repo.get(eid(84))
    assert invalid.value.code == PersistenceErrorCode.PERSISTED_DATA_INVALID

    conn.execute(
        "CREATE TRIGGER synthetic_snapshot_child_failure BEFORE INSERT "
        "ON application_snapshot_artifact_refs WHEN NEW.order_index = 1 "
        "BEGIN SELECT RAISE(ABORT, 'synthetic'); END"
    )
    rejected = snapshot_with_refs(application(), eid(87), (eid(88), eid(89)))
    with pytest.raises(PersistenceError) as constraint:
        repo.add(rejected)
    assert constraint.value.code == PersistenceErrorCode.PERSISTENCE_CONSTRAINT
    assert (
        conn.execute(
            "SELECT count(*) FROM application_snapshots WHERE id=?", (str(eid(87)),)
        ).fetchone()[0]
        == 0
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
