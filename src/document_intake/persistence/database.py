# ruff: noqa: E501, F405, F403, SIM105
"""Encrypted SQLCipher database facade."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self

from document_intake.application.ports.persistence import DatabaseKeyProvider
from document_intake.domain import *
from document_intake.persistence import serialization as ser
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode
from document_intake.persistence.migrations import (
    APPLICATION_ID,
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
)

Connection = Any


def _load_sqlcipher3() -> Any:
    try:
        return importlib.import_module("sqlcipher3")
    except ImportError:
        raise PersistenceError(PersistenceErrorCode.SQLCIPHER_UNAVAILABLE) from None


def _apply_raw_hex_key(connection: Connection, key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) != 32:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_INVALID)
    key_sql = "PRAGMA key = \"x'" + key.hex() + "'\""
    try:
        connection.execute(key_sql)
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_REJECTED) from None
    finally:
        key_sql = ""


def _fetch_one(connection: Connection, sql: str) -> Any:
    row = connection.execute(sql).fetchone()
    return None if row is None else row[0]


def _validate_key(provider: DatabaseKeyProvider) -> bytes:
    try:
        key = provider.get_database_key()
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_INVALID) from None
    if not isinstance(key, bytes) or len(key) != 32:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_INVALID)
    return key


def _open_connection(path: Path, provider: DatabaseKeyProvider) -> Connection:
    module = _load_sqlcipher3()
    key = _validate_key(provider)
    try:
        conn = module.connect(str(path), timeout=5.0, isolation_level=None)
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_OPEN_FAILED) from None
    try:
        _apply_raw_hex_key(conn, key)
        _harden_connection(conn)
    except PersistenceError:
        try:
            conn.close()
        finally:
            raise
    except Exception:
        try:
            conn.close()
        finally:
            raise PersistenceError(PersistenceErrorCode.DB_OPEN_FAILED) from None
    return conn


def _harden_connection(conn: Connection) -> None:
    try:
        status = _fetch_one(conn, "PRAGMA cipher_status")
        if status != "active":
            raise PersistenceError(PersistenceErrorCode.DB_ENCRYPTION_INACTIVE)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA temp_store = MEMORY")
        journal = _fetch_one(conn, "PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        conn.execute("PRAGMA trusted_schema = OFF")
        if int(_fetch_one(conn, "PRAGMA foreign_keys")) != 1:
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        if int(_fetch_one(conn, "PRAGMA temp_store")) != 2:
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        if str(journal).lower() != "wal":
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        if int(_fetch_one(conn, "PRAGMA synchronous")) != 2:
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        if int(_fetch_one(conn, "PRAGMA trusted_schema")) != 0:
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        rows = conn.execute("PRAGMA cipher_integrity_check").fetchall()
        if rows and any(str(row[0]).lower() != "ok" for row in rows):
            raise PersistenceError(PersistenceErrorCode.DB_INTEGRITY_FAILED)
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_REJECTED) from None


def _table_count(conn: Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0])


def _validate_schema(conn: Connection) -> None:
    user_version = int(_fetch_one(conn, "PRAGMA user_version"))
    if user_version > CURRENT_SCHEMA_VERSION:
        raise PersistenceError(PersistenceErrorCode.SCHEMA_VERSION_UNSUPPORTED)
    app_id = int(_fetch_one(conn, "PRAGMA application_id"))
    if user_version and app_id != APPLICATION_ID:
        raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
    if user_version == 0:
        if _table_count(conn) != 0:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
        return
    rows = conn.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    if len(rows) != user_version:
        raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
    expected_versions = tuple(range(1, user_version + 1))
    if tuple(int(r[0]) for r in rows) != expected_versions:
        raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
    for row, migration in zip(rows, MIGRATIONS, strict=True):
        if row[1] != migration.name:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
        if row[2] != migration.checksum:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_CHECKSUM_MISMATCH)


def _apply_migrations(conn: Connection) -> None:
    _validate_schema(conn)
    current = int(_fetch_one(conn, "PRAGMA user_version"))
    for migration in MIGRATIONS[current:]:
        try:
            conn.execute("BEGIN IMMEDIATE")
            if migration.version == 1:
                conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at_utc) VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (migration.version, migration.name, migration.checksum),
            )
            conn.execute(f"PRAGMA user_version = {migration.version}")
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise PersistenceError(PersistenceErrorCode.MIGRATION_FAILED) from None
    _validate_schema(conn)


class EncryptedDatabase:
    def __init__(self, path: Path, key_provider: DatabaseKeyProvider) -> None:
        self._path = Path(path)
        self._key_provider = key_provider

    def __repr__(self) -> str:
        return "EncryptedDatabase(<redacted>)"

    def initialize(self) -> None:
        if not self._path.parent.exists():
            raise PersistenceError(PersistenceErrorCode.DB_PARENT_MISSING)
        existed = self._path.exists()
        conn: Connection | None = None
        try:
            conn = _open_connection(self._path, self._key_provider)
            _apply_migrations(conn)
        except PersistenceError:
            if not existed:
                self._cleanup_new_database()
            raise
        finally:
            if conn is not None:
                conn.close()

    def _cleanup_new_database(self) -> None:
        for suffix in ("", "-wal", "-shm", "-journal"):
            target = Path(str(self._path) + suffix)
            try:
                if target.exists():
                    target.unlink()
            except OSError:
                pass

    def unit_of_work(self) -> SqlCipherUnitOfWork:
        return SqlCipherUnitOfWork(self._path, self._key_provider)


class _Repo:
    def __init__(
        self,
        uow: SqlCipherUnitOfWork,
        table: str,
        to_json: Callable[[Any], str],
        from_json: Callable[[str], Any],
    ) -> None:
        self._uow = uow
        self._table = table
        self._to_json = to_json
        self._from_json = from_json

    def __repr__(self) -> str:
        return f"Repository({self._table})"

    @property
    def c(self) -> Connection:
        return self._uow._connection()

    def _add(self, key: str, payload: str, extra: tuple[Any, ...] = ()) -> None:
        placeholders = ", ".join("?" for _ in (key, *extra, payload))
        cols = {
            "persons": "id, payload",
            "vehicles": "id, payload",
            "terminals": "code, is_active, payload",
            "identity_documents": "id, person_id, payload",
            "migration_documents": "id, person_id, related_passport_id, payload",
            "documents": "id, owner_kind, owner_id, payload",
            "field_candidates": "id, field_entity_id, field_key, confidence, payload",
            "applications": "id, terminal_code, payload",
            "application_snapshots": "id, application_id, terminal_code, created_at_utc, canonical_json, sha256, payload",
        }[self._table]
        try:
            self.c.execute(
                f"INSERT INTO {self._table} ({cols}) VALUES ({placeholders})",
                (key, *extra, payload),
            )
        except PersistenceError:
            raise
        except Exception:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS) from None

    def _update(
        self,
        key: str,
        payload: str,
        where_col: str = "id",
        extra_set: str = "",
        params: tuple[Any, ...] = (),
    ) -> None:
        cur = self.c.execute(
            f"UPDATE {self._table} SET payload=?{extra_set} WHERE {where_col}=?",
            (payload, *params, key),
        )
        if cur.rowcount != 1:
            raise PersistenceError(PersistenceErrorCode.ENTITY_NOT_FOUND)

    def _get(self, key: Any, where_col: str = "id") -> Any | None:
        row = self.c.execute(
            f"SELECT payload FROM {self._table} WHERE {where_col}=?", (key,)
        ).fetchone()
        return None if row is None else self._from_json(row[0])


class PersonRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "persons", ser.person_to_json, ser.person_from_json)

    def add(self, person: Person) -> None:
        self._add(str(person.id), self._to_json(person))

    def get(self, entity_id: EntityId) -> Person | None:
        return self._get(str(entity_id))

    def update(self, person: Person) -> None:
        self._update(str(person.id), self._to_json(person))

    def list_all(self) -> tuple[Person, ...]:
        return tuple(
            self._from_json(r[0]) for r in self.c.execute("SELECT payload FROM persons ORDER BY id")
        )


class IdentityRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "identity_documents", ser.identity_to_json, ser.identity_from_json)

    def add(self, document: IdentityDocument) -> None:
        self._add(str(document.id), self._to_json(document), (str(document.person_id),))

    def get(self, entity_id: EntityId) -> IdentityDocument | None:
        return self._get(str(entity_id))

    def update(self, document: IdentityDocument) -> None:
        self._update(str(document.id), self._to_json(document))

    def list_by_person(self, person_id: EntityId) -> tuple[IdentityDocument, ...]:
        return tuple(
            self._from_json(r[0])
            for r in self.c.execute(
                "SELECT payload FROM identity_documents WHERE person_id=? ORDER BY id",
                (str(person_id),),
            )
        )


class MigrationRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "migration_documents", ser.migration_to_json, ser.migration_from_json)

    def add(self, document: MigrationDocument) -> None:
        self._add(
            str(document.id),
            self._to_json(document),
            (
                str(document.person_id),
                None if document.related_passport_id is None else str(document.related_passport_id),
            ),
        )

    def get(self, entity_id: EntityId) -> MigrationDocument | None:
        return self._get(str(entity_id))

    def update(self, document: MigrationDocument) -> None:
        self._update(str(document.id), self._to_json(document))

    def list_by_person(self, person_id: EntityId) -> tuple[MigrationDocument, ...]:
        return tuple(
            self._from_json(r[0])
            for r in self.c.execute(
                "SELECT payload FROM migration_documents WHERE person_id=? ORDER BY id",
                (str(person_id),),
            )
        )


class VehicleRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "vehicles", ser.vehicle_to_json, ser.vehicle_from_json)

    def add(self, vehicle: Vehicle) -> None:
        self._add(str(vehicle.id), self._to_json(vehicle))

    def get(self, entity_id: EntityId) -> Vehicle | None:
        return self._get(str(entity_id))

    def update(self, vehicle: Vehicle) -> None:
        self._update(str(vehicle.id), self._to_json(vehicle))

    def list_all(self) -> tuple[Vehicle, ...]:
        return tuple(
            self._from_json(r[0])
            for r in self.c.execute("SELECT payload FROM vehicles ORDER BY id")
        )


class TerminalRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "terminals", ser.terminal_to_json, ser.terminal_from_json)

    def add(self, terminal: Terminal) -> None:
        self._add(terminal.code.value, self._to_json(terminal), (1 if terminal.is_active else 0,))

    def get(self, code: TerminalCode) -> Terminal | None:
        return self._get(code.value, "code")

    def update(self, terminal: Terminal) -> None:
        self._update(
            terminal.code.value,
            self._to_json(terminal),
            "code",
            ", is_active=?",
            (1 if terminal.is_active else 0,),
        )

    def list_active(self) -> tuple[Terminal, ...]:
        return tuple(
            self._from_json(r[0])
            for r in self.c.execute("SELECT payload FROM terminals WHERE is_active=1 ORDER BY code")
        )


class DocumentRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "documents", ser.document_to_json, ser.document_from_json)

    def add(self, document: Document) -> None:
        owner = document.owner_ref
        self._add(
            str(document.id),
            self._to_json(document),
            (
                None if owner is None else owner.owner_kind.value,
                None if owner is None else str(owner.owner_id),
            ),
        )
        for i, sid in enumerate(document.side_ids):
            self.c.execute(
                "INSERT INTO document_sides(document_id, order_index, side_id) VALUES (?,?,?)",
                (str(document.id), i, str(sid)),
            )

    def get(self, entity_id: EntityId) -> Document | None:
        return self._get(str(entity_id))

    def update(self, document: Document) -> None:
        self.c.execute("DELETE FROM document_sides WHERE document_id=?", (str(document.id),))
        self._update(str(document.id), self._to_json(document))
        [
            self.c.execute(
                "INSERT INTO document_sides(document_id, order_index, side_id) VALUES (?,?,?)",
                (str(document.id), i, str(s)),
            )
            for i, s in enumerate(document.side_ids)
        ]

    def list_by_owner(self, owner_ref: OwnerRef) -> tuple[Document, ...]:
        return tuple(
            self._from_json(r[0])
            for r in self.c.execute(
                "SELECT payload FROM documents WHERE owner_kind=? AND owner_id=? ORDER BY id",
                (owner_ref.owner_kind.value, str(owner_ref.owner_id)),
            )
        )


class CandidateRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "field_candidates", ser.candidate_to_json, ser.candidate_from_json)

    def add(self, candidate: FieldCandidate) -> None:
        self._add(
            str(candidate.id),
            self._to_json(candidate),
            (
                str(candidate.field_ref.entity_id),
                candidate.field_ref.field_key.value,
                str(candidate.confidence.value),
            ),
        )
        for i, v in enumerate(candidate.validation_results):
            self.c.execute(
                "INSERT INTO field_candidate_validation_results(candidate_id, order_index, result) VALUES (?,?,?)",
                (str(candidate.id), i, v.value),
            )

    def get(self, entity_id: EntityId) -> FieldCandidate | None:
        return self._get(str(entity_id))

    def list_for_field(self, field_ref: FieldRef) -> tuple[FieldCandidate, ...]:
        return tuple(
            self._from_json(r[0])
            for r in self.c.execute(
                "SELECT payload FROM field_candidates WHERE field_entity_id=? AND field_key=? ORDER BY id",
                (str(field_ref.entity_id), field_ref.field_key.value),
            )
        )


class ApplicationRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "applications", ser.application_to_json, ser.application_from_json)

    def add(self, application: Application) -> None:
        self._add(
            str(application.id),
            self._to_json(application),
            (None if application.terminal_code is None else application.terminal_code.value,),
        )
        self._children(application)

    def get(self, entity_id: EntityId) -> Application | None:
        return self._get(str(entity_id))

    def update(self, application: Application) -> None:
        self.c.execute(
            "DELETE FROM application_assignments WHERE application_id=?", (str(application.id),)
        )
        self.c.execute(
            "DELETE FROM application_verified_fields WHERE application_id=?", (str(application.id),)
        )
        self.c.execute(
            "DELETE FROM application_validation_issues WHERE application_id=?",
            (str(application.id),),
        )
        self._update(str(application.id), self._to_json(application))
        self._children(application)

    def _children(self, a: Application) -> None:
        for i, x in enumerate(a.assignments):
            self.c.execute(
                "INSERT INTO application_assignments(application_id, order_index, person_id, tractor_id, trailer_id, payload) VALUES (?,?,?,?,?,?)",
                (
                    str(a.id),
                    i,
                    str(x.person_id),
                    str(x.tractor_id),
                    None if x.trailer_id is None else str(x.trailer_id),
                    ser.dumps(ser._assignment_to_dict(x)),
                ),
            )
        for verified_field in a.verified_fields:
            self.c.execute(
                "INSERT INTO application_verified_fields(application_id, field_entity_id, field_key, source_candidate_id, payload) VALUES (?,?,?,?,?)",
                (
                    str(a.id),
                    str(verified_field.field_ref.entity_id),
                    verified_field.field_ref.field_key.value,
                    None
                    if verified_field.source_candidate_id is None
                    else str(verified_field.source_candidate_id),
                    ser.dumps(ser._verified_to_dict(verified_field)),
                ),
            )
        for issue_index, issue in enumerate(a.validation_report.issues):
            self.c.execute(
                "INSERT INTO application_validation_issues(application_id, order_index, payload) VALUES (?,?,?)",
                (str(a.id), issue_index, ser.dumps(ser._issue_to_dict(issue))),
            )


class SnapshotRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(uow, "application_snapshots", ser.snapshot_to_json, ser.snapshot_from_json)

    def add(self, snapshot: ApplicationSnapshot) -> None:
        self._add(
            str(snapshot.id),
            self._to_json(snapshot),
            (
                str(snapshot.application_id),
                snapshot.terminal_code.value,
                ser.utc_iso(snapshot.created_at),
                snapshot.payload.canonical_json,
                snapshot.sha256,
            ),
        )
        for i, x in enumerate(snapshot.document_artifact_refs):
            self.c.execute(
                "INSERT INTO application_snapshot_artifact_refs(snapshot_id, order_index, artifact_ref) VALUES (?,?,?)",
                (str(snapshot.id), i, str(x)),
            )

    def get(self, entity_id: EntityId) -> ApplicationSnapshot | None:
        return self._get(str(entity_id))

    def list_by_application(self, application_id: EntityId) -> tuple[ApplicationSnapshot, ...]:
        return tuple(
            self._from_json(r[0])
            for r in self.c.execute(
                "SELECT payload FROM application_snapshots WHERE application_id=? ORDER BY created_at_utc, id",
                (str(application_id),),
            )
        )


class SqlCipherUnitOfWork:
    def __init__(self, path: Path, key_provider: DatabaseKeyProvider) -> None:
        self._path = path
        self._key_provider = key_provider
        self._conn: Connection | None = None
        self._closed = False
        self._entered = False
        self._committed = False
        self.persons = PersonRepo(self)
        self.identity_documents = IdentityRepo(self)
        self.migration_documents = MigrationRepo(self)
        self.vehicles = VehicleRepo(self)
        self.terminals = TerminalRepo(self)
        self.documents = DocumentRepo(self)
        self.field_candidates = CandidateRepo(self)
        self.applications = ApplicationRepo(self)
        self.application_snapshots = SnapshotRepo(self)

    def __repr__(self) -> str:
        return "SqlCipherUnitOfWork(<redacted>)"

    def _connection(self) -> Connection:
        if self._closed or self._conn is None:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        return self._conn

    def __enter__(self) -> Self:
        if self._closed or self._entered:
            raise PersistenceError(PersistenceErrorCode.UOW_STATE)
        self._conn = _open_connection(self._path, self._key_provider)
        _validate_schema(self._conn)
        if int(_fetch_one(self._conn, "PRAGMA user_version")) != CURRENT_SCHEMA_VERSION:
            self._conn.close()
            self._closed = True
            raise PersistenceError(PersistenceErrorCode.SCHEMA_VERSION_UNSUPPORTED)
        self._conn.execute("BEGIN IMMEDIATE")
        self._entered = True
        return self

    def commit(self) -> None:
        if self._closed:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        if not self._entered or self._conn is None:
            raise PersistenceError(PersistenceErrorCode.UOW_STATE)
        self._conn.execute("COMMIT")
        self._committed = True

    def rollback(self) -> None:
        if self._closed:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        if self._conn is not None:
            self._conn.execute("ROLLBACK")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            if self._conn is not None and not self._committed:
                try:
                    self._conn.execute("ROLLBACK")
                except Exception:
                    pass
        finally:
            if self._conn is not None:
                self._conn.close()
            self._closed = True
        return False
